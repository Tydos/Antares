from typing import Literal
from pydantic import BaseModel


class UploadCompleteRequest(BaseModel):
    filename: str
    blobUrl: str


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    filenames: list[str] | None = None
    search_mode: Literal["hybrid", "semantic", "keyword"] = "hybrid"
    source_type: Literal["pdf", "advisory"] | None = None


class IngestPackageRequest(BaseModel):
    name: str
    ecosystem: Literal["PyPI", "npm", "Go", "crates.io", "Maven", "RubyGems"] = "PyPI"


ChatRequest = QueryRequest
