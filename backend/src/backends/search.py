from elasticsearch import Elasticsearch
from elasticsearch.exceptions import BadRequestError
from datetime import datetime, timezone
import logging
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
        """Return a summary list of all indexed PDFs.

        Uses a terms aggregation to group pages by filename, returning one entry per file
        with its total page count and the timestamp of its most recent upload.
        """
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
                    }
                }
            }
        )
        return [
            {
                "filename":    bucket["key"],
                "page_count":  int(bucket["pages"]["value"]),
                "uploaded_at": bucket["uploaded_at"]["value_as_string"],
                "embedded":    bucket["embedded_pages"]["doc_count"] == bucket["doc_count"],
            }
            for bucket in response["aggregations"]["by_file"]["buckets"]
        ]
