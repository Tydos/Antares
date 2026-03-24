from src.storage import MinioStorageBackend
from src.search import ElasticsearchSearchBackend
from src.pdf import extract_text_pages
import os
import logging


class IndexingService:
    def __init__(self, storage: MinioStorageBackend, search: ElasticsearchSearchBackend) -> None:
        self._storage = storage
        self._search = search

    def index_document(self, filename: str, url: str) -> None:
        """Download PDF, extract pages, index each one into Elasticsearch."""
        tmp_path = self._storage.download_to_tempfile(filename)
        try:
            for page_number, content in extract_text_pages(tmp_path):
                logging.debug(f"Indexing {filename} page {page_number}")
                self._search.index_page(filename, url, page_number, content)
        finally:
            os.remove(tmp_path)
        logging.info(f"Indexing complete: {filename}")
