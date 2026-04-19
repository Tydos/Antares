import os
import tempfile
import logging
import urllib.request

from src.document_store import DocumentStore
from src.pdf_reader import extract_text_pages


class IngestionPipeline:
    def __init__(self, store: DocumentStore) -> None:
        self.store = store

    def index_document(self, filename: str, blob_url: str) -> None:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp_path = tmp.name
            urllib.request.urlretrieve(blob_url, tmp_path)

            pages = [
                (page_number, text)
                for page_number, text in extract_text_pages(tmp_path)
                if text.strip()
            ]

            if not pages:
                logging.warning(f"No text extracted from {filename}, marking skipped.")
                self.store.set_upload_status(filename, "skipped", 0)
                return

            logging.info(f"Processed {filename} ({len(pages)} text pages)")
            self.store.set_upload_status(filename, "indexed", len(pages))

        except Exception:
            logging.exception(f"Ingestion failed: {filename}")
            try:
                self.store.set_upload_status(filename, "failed", 0)
            except Exception:
                logging.exception(f"Could not mark upload failed for {filename}")

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
