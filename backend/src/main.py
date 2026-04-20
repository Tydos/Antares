import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.answerer import generate_answer
from src.config import settings
from src.database import Database, create_connection_pool
from src.embedder import embed
from src.pipeline import Pipeline
from src.vercel_blob import BlobTokenError, handle_upload_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
    stream=sys.stdout,
)

_MAX_PDF_BYTES = 100 * 1024 * 1024
_PDF_CONTENT_TYPES = ("application/pdf", "application/x-pdf", "application/octet-stream")


# --- App startup ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = create_connection_pool()
    app.state.db = Database(pool)
    app.state.pipeline = Pipeline(app.state.db)
    yield


app = FastAPI(title="RAG PDF API", lifespan=lifespan)
router = APIRouter()


# --- Dependency helpers ---

def get_db(request: Request) -> Database:
    return request.app.state.db


def get_pipeline(request: Request) -> Pipeline:
    return request.app.state.pipeline


# --- Routes ---

@router.get("/")
def root():
    return {"message": "RAG PDF API. Visit /docs for the interactive API explorer."}


@router.get("/health")
def health(db: Database = Depends(get_db)):
    db_ok = db.ping()
    return JSONResponse(
        {"status": "ok" if db_ok else "degraded", "services": {"database": db_ok}},
        status_code=200 if db_ok else 503,
    )


class UploadCompleteRequest(BaseModel):
    filename: str
    blobUrl: str


@router.post("/blob-upload")
def blob_upload(body: dict[str, Any]):
    """Step 1 of the upload flow: browser asks for a signed token to upload directly to Vercel Blob."""
    try:
        return handle_upload_event(
            body,
            settings.blob_read_write_token.strip(),
            allowed_content_types=list(_PDF_CONTENT_TYPES),
            maximum_size_in_bytes=_MAX_PDF_BYTES,
        )
    except BlobTokenError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e


@router.post("/upload-complete")
def upload_complete(
    req: UploadCompleteRequest,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_db),
    pipeline: Pipeline = Depends(get_pipeline),
):
    """Step 2 of the upload flow: browser notifies us the PDF is in blob storage so we can index it."""
    db.add_upload(req.filename, req.blobUrl)
    background_tasks.add_task(pipeline.index_document, req.filename, req.blobUrl)
    return {"status": "upload recorded, indexing in progress"}


@router.get("/documents")
def list_documents(db: Database = Depends(get_db)):
    return {"documents": db.list_uploads()}


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    filenames: list[str] | None = None


@router.post("/query")
def query(req: QueryRequest, db: Database = Depends(get_db)):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    top_k = max(1, min(req.top_k, 20))

    try:
        query_vector = embed([question])[0]
    except Exception as e:
        logging.exception("Embedding failed")
        raise HTTPException(status_code=503, detail=f"Embedding service error: {e}")

    chunks = db.search_chunks(query_vector, k=top_k, filenames=req.filenames or None)

    answer: str | None = None
    try:
        answer = generate_answer(question, chunks)
    except Exception:
        logging.exception("Answer generation failed; returning raw chunks")

    return {"question": question, "answer": answer, "chunks": chunks}


@router.delete("/files/{filename}")
def delete_file(filename: str, db: Database = Depends(get_db)):
    try:
        db.remove_upload(filename)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"deleted": filename}


app.include_router(router)
