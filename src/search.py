from elasticsearch import Elasticsearch
from elasticsearch.exceptions import BadRequestError
from datetime import datetime, timezone
import logging


_INDEX_MAPPINGS = {
    "properties": {
        "filename":    {"type": "keyword"},
        "url":         {"type": "keyword"},
        "page_number": {"type": "integer"},
        "content":     {"type": "text"},
        "uploaded_at": {"type": "date"}
    }
}


class ElasticsearchSearchBackend:
    def __init__(self, client: Elasticsearch, index_name: str) -> None:
        self._client = client
        self._index = index_name
        try:
            self._client.indices.create(index=self._index, mappings=_INDEX_MAPPINGS)
            logging.debug(f"Created index: {self._index}")
        except BadRequestError as e:
            if "resource_already_exists_exception" not in str(e):
                raise

    def ping(self) -> bool:
        """Return True if the Elasticsearch cluster is reachable."""
        return self._client.ping()

    def index_page(self, filename: str, url: str, page_number: int, content: str) -> None:
        doc = {
            "filename":    filename,
            "url":         url,
            "page_number": page_number,
            "content":     content,
            "uploaded_at": datetime.now(timezone.utc).isoformat()
        }
        res = self._client.index(index=self._index, document=doc)
        logging.debug(f"Indexed page {page_number} of {filename}: {res['result']}")

    def keyword_search(self, query: str, top_k: int = 5) -> list[dict]:
        """Full-text match against content; returns hits with relevance score."""
        resp = self._client.search(
            index=self._index,
            query={
                "match": {
                    "content": {
                        "query": query,
                        "operator": "or"
                    }
                }
            },
            highlight={
                "fields": {"content": {"fragment_size": 200, "number_of_fragments": 2}}
            },
            size=top_k
        )
        results = []
        for hit in resp["hits"]["hits"]:
            entry = {"score": hit["_score"], **hit["_source"]}
            if "highlight" in hit:
                entry["highlights"] = hit["highlight"].get("content", [])
            results.append(entry)
        return results

    def list_documents(self) -> list[dict]:
        """Return one summary row per unique filename (aggregation)."""
        resp = self._client.search(
            index=self._index,
            size=0,
            aggs={
                "by_file": {
                    "terms": {"field": "filename", "size": 100},
                    "aggs": {
                        "pages":       {"max": {"field": "page_number"}},
                        "uploaded_at": {"max": {"field": "uploaded_at"}}
                    }
                }
            }
        )
        return [
            {
                "filename":    bucket["key"],
                "page_count":  int(bucket["pages"]["value"]),
                "uploaded_at": bucket["uploaded_at"]["value_as_string"],
            }
            for bucket in resp["aggregations"]["by_file"]["buckets"]
        ]
