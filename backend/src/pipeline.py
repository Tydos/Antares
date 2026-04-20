import os
import tempfile
import logging
import urllib.request

from src.database import Database
from src.embedder import embed
from src.pdf import extract_text_pages


_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 100


def _split_into_chunks(text: str, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP):
    """Yield non-empty text chunks with a sliding window."""
    step = max(1, size - overlap)
    i = 0
    while i < len(text):
        piece = text[i : i + size].strip()
        if piece:
            yield piece
        i += step


class Pipeline:
    """Download a PDF, extract text, embed it, and store chunks in the database."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def index_document(self, filename: str, blob_url: str) -> None:
        tmp_path = None
        try:
            # Download the PDF to a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp_path = tmp.name
            urllib.request.urlretrieve(blob_url, tmp_path)

            # Extract text from every page and split into overlapping chunks
            pages: list[int] = []
            indexes: list[int] = []
            texts: list[str] = []
            page_count = 0

            for page_number, page_text in extract_text_pages(tmp_path):
                if not page_text.strip():
                    continue
                page_count += 1
                for chunk_idx, chunk in enumerate(_split_into_chunks(page_text)):
                    pages.append(page_number)
                    indexes.append(chunk_idx)
                    texts.append(chunk)

            if not texts:
                logging.warning(f"No text found in {filename}, marking as skipped.")
                self.db.set_status(filename, "skipped", 0)
                return

            # Embed all chunks and store them
            vectors = embed(texts)
            if len(vectors) != len(texts):
                raise RuntimeError(
                    f"Embedding count mismatch: got {len(vectors)} for {len(texts)} chunks"
                )

            self.db.delete_chunks(filename)
            self.db.save_chunks(filename, pages, indexes, texts, vectors)

            logging.info(f"Indexed {filename}: {page_count} pages, {len(texts)} chunks")
            self.db.set_status(filename, "indexed", page_count)

        except Exception:
            logging.exception(f"Indexing failed for {filename}")
            try:
                self.db.set_status(filename, "failed", 0)
            except Exception:
                logging.exception(f"Could not mark {filename} as failed")

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
