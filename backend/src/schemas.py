from pydantic import BaseModel

class UploadCompleteRequest(BaseModel):
    filename: str
    blobUrl: str

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    filenames: list[str] | None = None
