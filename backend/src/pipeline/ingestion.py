import os
import tempfile
import logging
import urllib.request
from src.backends.search import ElasticsearchSearchBackend
from src.backends.embeddings import TextEncoder
from src.utils.pdf_reader import extract_text_pages
from src.config import settings


class IngestionPipeline:
    def __init__(
        self,
        search: ElasticsearchSearchBackend,
        embeddings: TextEncoder,
    ) -> None:
        self.search = search
        self.embeddings = embeddings

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
                logging.warning(f"No text extracted from {filename}, skipping index.")
                return

            new_docs = []
            for i in range(0, len(pages), settings.batch_size):
                batch = pages[i : i + settings.batch_size]
                texts = [text for _, text in batch]
                vectors = self.embeddings.encode(texts)
                for (page_number, text), vector in zip(batch, vectors):
                    new_docs.append((page_number, text, vector))

            self.search.delete_page(filename)
            for page_number, text, vector in new_docs:
                self.search.index_page(filename, page_number, text, vector)

            logging.info(f"Indexed {filename} ({len(pages)} pages)")

        except Exception:
            logging.exception(f"Indexing failed: {filename}")

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
