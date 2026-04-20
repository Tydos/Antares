from collections.abc import Generator
from pypdf import PdfReader


def extract_text_pages(file_path: str) -> Generator[tuple[int, str], None, None]:
    """Yield (page_number, text) for every page in a PDF file. Page numbers start at 1."""
    reader = PdfReader(file_path)
    for page_number, page in enumerate(reader.pages, start=1):
        yield page_number, page.extract_text() or ""
