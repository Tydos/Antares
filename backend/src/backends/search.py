import hashlib
import logging
from datetime import datetime, timezone

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import BadRequestError, NotFoundError

from src.config import settings


_INDEX_MAPPINGS = {
    "properties": {
        "filename":    {"type": "keyword"},
        "page_number": {"type": "integer"},
        "content":     {"type": "text"},
        "uploaded_at": {"type": "date"},
        "embedding":   {"type": "dense_vector", "dims": settings.embedding_dims, "index": True, "similarity": "cosine"}
    }
}

_UPLOADS_MAPPINGS = {
    "properties": {
        "filename":    {"type": "keyword"},
        "blob_url":    {"type": "keyword"},
        "uploaded_at": {"type": "date"},
        "status":      {"type": "keyword"},
        "page_count":  {"type": "integer"},
    }
}


def _upload_doc_id(filename: str) -> str:
    return hashlib.sha256(filename.encode("utf-8")).hexdigest()


class ElasticsearchSearchBackend:
    """Wraps the Elasticsearch client to provide indexing and search for PDF pages.

    On startup it creates the index if it does not exist, or attempts to update
    the mapping if the index is already present.

    Each indexed document represents one page of a PDF and contains:
      - filename    : the original PDF filename (used as a grouping key)
      - page_number : 1-based page index
      - content     : extracted plain text
      - uploaded_at : UTC timestamp of when the file was uploaded
      - embedding   : dense vector for semantic (kNN) search
    """

    def __init__(self, client: Elasticsearch, index_name: str) -> None:
        """Connect to Elasticsearch and ensure the index exists with the correct mapping."""
        self._client = client
        self._index = index_name
        self._uploads_index = f"{index_name}-uploads"
        try:
            self._client.indices.create(index=self._index, mappings=_INDEX_MAPPINGS)
            logging.debug(f"Created index: {self._index}")
        except BadRequestError as e:
            if "resource_already_exists_exception" not in str(e):
                raise
            try:
                self._client.indices.put_mapping(index=self._index, properties=_INDEX_MAPPINGS["properties"])
            except Exception:
                logging.warning(f"Could not update mapping for index '{self._index}' — it may be out of date.")

        try:
            self._client.indices.create(index=self._uploads_index, mappings=_UPLOADS_MAPPINGS)
            logging.debug(f"Created uploads index: {self._uploads_index}")
        except BadRequestError as e:
            if "resource_already_exists_exception" not in str(e):
                raise
            try:
                self._client.indices.put_mapping(
                    index=self._uploads_index, properties=_UPLOADS_MAPPINGS["properties"]
                )
            except Exception:
                logging.warning(
                    f"Could not update mapping for uploads index '{self._uploads_index}' — it may be out of date."
                )

    def ping_es(self) -> bool:
        """Return True if the Elasticsearch cluster is reachable."""
        return self._client.ping()

    def index_page(self, filename: str, page_number: int, content: str, embedding: list[float] | None = None) -> None:
        """Store a single PDF page in the index.

        The embedding is optional — pages without one can still be found by keyword search.
        """
        doc = {
            "filename":    filename,
            "page_number": page_number,
            "content":     content,
            "uploaded_at": datetime.now(timezone.utc).isoformat()
        }
        if embedding is not None:
            doc["embedding"] = embedding
        response = self._client.index(index=self._index, document=doc)
        logging.debug(f"Indexed page {page_number} of {filename}: {response['result']}")

    def delete_page(self, filename: str) -> None:
        """Remove all indexed pages for a given filename.

        Called before re-indexing a file to prevent duplicate pages.
        Uses refresh=True so the deletions are visible to the next search immediately.
        """
        self._client.delete_by_query(
            index=self._index,
            query={"term": {"filename": filename}},
            refresh=True
        )
        logging.debug(f"Deleted existing pages for: {filename}")

    def record_upload(self, filename: str, blob_url: str) -> None:
        """Persist one row per Vercel upload so /documents can list files before indexing finishes."""
        doc = {
            "filename":    filename,
            "blob_url":    blob_url,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "status":      "pending",
            "page_count":  0,
        }
        self._client.index(
            index=self._uploads_index,
            id=_upload_doc_id(filename),
            document=doc,
            refresh=True,
        )

    def set_upload_status(self, filename: str, status: str, page_count: int = 0) -> None:
        """Update ingestion outcome (indexed / skipped / failed)."""
        self._client.update(
            index=self._uploads_index,
            id=_upload_doc_id(filename),
            doc={"status": status, "page_count": page_count},
            refresh=True,
        )

    def delete_upload_record(self, filename: str) -> None:
        try:
            self._client.delete(
                index=self._uploads_index, id=_upload_doc_id(filename), refresh=True
            )
        except NotFoundError:
            pass

    def _aggregate_indexed_files(self) -> dict[str, dict]:
        response = self._client.search(
            index=self._index,
            size=0,
            aggs={
                "by_file": {
                    "terms": {"field": "filename", "size": 10000},
                    "aggs": {
                        "pages":          {"max": {"field": "page_number"}},
                        "uploaded_at":    {"max": {"field": "uploaded_at"}},
                        "embedded_pages": {"filter": {"exists": {"field": "embedding"}}},
                    },
                }
            },
        )
        out: dict[str, dict] = {}
        for bucket in response["aggregations"]["by_file"]["buckets"]:
            fn = bucket["key"]
            out[fn] = {
                "page_count":  int(bucket["pages"]["value"]),
                "uploaded_at": bucket["uploaded_at"]["value_as_string"],
                "embedded":    bucket["embedded_pages"]["doc_count"] == bucket["doc_count"],
            }
        return out

    def hybrid_search(self, query: str, query_vector: list[float], top_k: int = 5) -> list[dict]:
        """Combine BM25 and kNN results using Reciprocal Rank Fusion (RRF).

        Each retriever scores documents independently over a larger candidate pool.
        RRF then merges the two ranked lists:  score = Σ 1 / (k + rank),  k=60.
        Documents that rank highly in both lists rise to the top.
        """
        pool = max(100, top_k * 10)

        #keyword search with BM25 and fuzzy matching to handle OCR errors, plus highlights for matched terms
        bm25_hits = self._client.search(
            index=self._index,
            query={"match": {"content": {"query": query, "fuzziness": "AUTO", "prefix_length": 1}}},
            highlight={"fields": {"content": {"fragment_size": 200, "number_of_fragments": 2}}},
            source={"excludes": ["embedding"]},
            size=pool,
        )["hits"]["hits"]

        #vector search with cosine similarity over the "embedding" field, no highlights since it's a semantic match
        knn_hits = self._client.search(
            index=self._index,
            knn={"field": "embedding", "query_vector": query_vector, "num_candidates": pool, "k": pool},
            source={"excludes": ["embedding"]},
            size=pool,
        )["hits"]["hits"]

        # RRF: accumulate 1/(k+rank) per document across both ranked lists
        RRF_K = 60
        scores: dict[str, float] = {}
        meta:   dict[str, dict]  = {}

        for rank, hit in enumerate(bm25_hits, start=1):
            doc_id = hit["_id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
            if doc_id not in meta:
                meta[doc_id] = {"source": hit["_source"], "highlights": hit.get("highlight", {}).get("content", [])}

        for rank, hit in enumerate(knn_hits, start=1):
            doc_id = hit["_id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
            if doc_id not in meta:
                meta[doc_id] = {"source": hit["_source"], "highlights": []}

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for doc_id, rrf_score in ranked:
            result = {"score": round(rrf_score, 6), **meta[doc_id]["source"]}
            if meta[doc_id]["highlights"]:
                result["highlights"] = meta[doc_id]["highlights"]
            results.append(result)
        return results

    def list_documents(self) -> list[dict]:
        """Return every known upload (Vercel) plus legacy rows that only exist in the page index."""
        upload_hits = self._client.search(
            index=self._uploads_index,
            size=10000,
            sort=[{"uploaded_at": {"order": "desc"}}],
            query={"match_all": {}},
        )["hits"]["hits"]

        by_name: dict[str, dict] = {}
        for hit in upload_hits:
            src = hit["_source"]
            fn = src["filename"]
            by_name[fn] = {
                "filename":    fn,
                "blob_url":    src.get("blob_url", ""),
                "page_count":  int(src.get("page_count") or 0),
                "uploaded_at": src.get("uploaded_at"),
                "status":      src.get("status", "pending"),
                "embedded":    src.get("status") == "indexed" and int(src.get("page_count") or 0) > 0,
            }

        indexed_only = self._aggregate_indexed_files()
        for fn, meta in indexed_only.items():
            if fn in by_name:
                if by_name[fn]["status"] == "indexed":
                    by_name[fn]["embedded"] = meta["embedded"]
                continue
            by_name[fn] = {
                "filename":    fn,
                "blob_url":    "",
                "page_count":  meta["page_count"],
                "uploaded_at": meta["uploaded_at"],
                "status":      "indexed",
                "embedded":    meta["embedded"],
            }

        for fn, row in by_name.items():
            if fn in indexed_only and row.get("status") == "indexed":
                row["page_count"] = indexed_only[fn]["page_count"]
                row["embedded"] = indexed_only[fn]["embedded"]

        rows = list(by_name.values())

        def _sort_key(row: dict) -> str:
            u = row.get("uploaded_at") or ""
            return u if isinstance(u, str) else ""

        rows.sort(key=_sort_key, reverse=True)
        return rows
