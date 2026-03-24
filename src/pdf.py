from typing import Tuple, Generator
from PyPDF2 import PdfReader

def extract_text_pages(file_path: str) -> Generator[Tuple[int, str], None, None]:
    """Yield (page_number, text) for every page in a local PDF file."""
    reader = PdfReader(file_path)
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        yield page_number, text
