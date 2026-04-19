import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.blob_client_token import generate_client_token_from_read_write_token
from src.config import settings
from src.document_store import DocumentStore
from src.ingestion import IngestionPipeline
from src.services import init_services, get_store, get_indexing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
    stream=sys.stdout,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_services(app)
    yield


app = FastAPI(title="RAG PDF API", lifespan=lifespan)
router = APIRouter()

_MAX_PDF_BYTES = 100 * 1024 * 1024
_PDF_CONTENT_TYPES = ("application/pdf", "application/x-pdf", "application/octet-stream")


@router.get("/")
def root():
    return {"message": "Welcome to the RAG PDF API. Use /docs for interactive API docs."}


@router.get("/health")
def health(store: DocumentStore = Depends(get_store)):
    db_ok = store.ping()
    return JSONResponse(
        {"status": "ok" if db_ok else "degraded", "services": {"database": db_ok}},
        status_code=200 if db_ok else 503,
    )


class UploadCompleteRequest(BaseModel):
    filename: str
    blobUrl: str


@router.post("/blob-upload")
def blob_upload(body: dict[str, Any]):
    """Vercel Blob handleUpload-compatible endpoint (@vercel/blob client upload())."""
    token = settings.blob_read_write_token.strip()
    if not token:
        raise HTTPException(status_code=503, detail="BLOB_READ_WRITE_TOKEN is not configured.")

    event_type = body.get("type")
    if event_type != "blob.generate-client-token":
        raise HTTPException(status_code=400, detail=f"Unsupported event type: {event_type!r}")

    payload = body.get("payload") or {}
    pathname = payload.get("pathname")
    if not pathname or not isinstance(pathname, str):
        raise HTTPException(status_code=400, detail="Missing payload.pathname")

    valid_until = int(time.time() * 1000) + 60 * 60 * 1000

    try:
        client_token = generate_client_token_from_read_write_token(
            read_write_token=token,
            pathname=pathname,
            valid_until_ms=valid_until,
            allowed_content_types=list(_PDF_CONTENT_TYPES),
            maximum_size_in_bytes=_MAX_PDF_BYTES,
            add_random_suffix=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return {"type": "blob.generate-client-token", "clientToken": client_token}


@router.post("/upload-complete")
def upload_complete(
    req: UploadCompleteRequest,
    background_tasks: BackgroundTasks,
    indexing: IngestionPipeline = Depends(get_indexing),
    store: DocumentStore = Depends(get_store),
):
    store.record_upload(req.filename, req.blobUrl)
    background_tasks.add_task(indexing.index_document, req.filename, req.blobUrl)
    return {"status": "upload recorded, indexing in progress"}


@router.get("/documents")
def list_documents(store: DocumentStore = Depends(get_store)):
    return {"documents": store.list_documents()}


@router.delete("/files/{filename}")
def delete_file(filename: str, store: DocumentStore = Depends(get_store)):
    try:
        store.delete_upload_record(filename)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"deleted": filename}


app.include_router(router, prefix=settings.route_prefix)
