from src.storage import MinioStorageBackend
from src.search import ElasticsearchSearchBackend
from src.pdf import extract_text_pages
import os
import logging


class IndexingService:
    def __init__(self, storage: MinioStorageBackend, search: ElasticsearchSearchBackend) -> None:
        self._storage = storage
        self._search = search

    def index_document(self, filename: str) -> None:
        """Delete stale pages, download PDF, extract and index each page.

        Runs as a FastAPI BackgroundTask — all exceptions are caught and logged
        so failures are never silently swallowed by the background runner.
        """
        tmp_path: str | None = None
        try:
            self._search.delete_document_pages(filename)
            tmp_path = self._storage.download_to_tempfile(filename)
            pages_indexed = 0
            for page_number, content in extract_text_pages(tmp_path):
                logging.debug(f"Indexing {filename} page {page_number}")
                self._search.index_page(filename, page_number, content)
                pages_indexed += 1
            logging.info(f"Indexing complete: {filename} ({pages_indexed} pages)")
        except Exception:
            logging.exception(f"Indexing failed for '{filename}'")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
