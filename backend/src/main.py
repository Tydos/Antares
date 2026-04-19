import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, Query
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import src.utils.logger  # noqa: F401 — configures root logger as a side effect
from src.backends.search import ElasticsearchSearchBackend
from src.blob_client_token import generate_client_token_from_read_write_token
from src.config import settings
from src.pipeline.ingestion import IngestionPipeline
from src.services import init_services, get_search, get_indexing, get_embeddings
from src.backends.embeddings import TextEncoder


@asynccontextmanager
async def lifespan(app: FastAPI):
    services = init_services()
    app.state.search     = services["search"]
    app.state.indexing   = services["indexing"]
    app.state.embeddings = services["embeddings"]
    yield


app = FastAPI(title="RAG PDF Hybrid Search", lifespan=lifespan)


@app.get("/")
def root():
    return {"message": "Welcome to the RAG PDF Hybrid Search API. Use /docs for interactive API docs."}


@app.get("/health")
def health(search: ElasticsearchSearchBackend = Depends(get_search)):
    checks = {"elasticsearch": search.ping_es()}
    ok = all(checks.values())
    return JSONResponse({"status": "ok" if ok else "degraded", "services": checks}, status_code=200 if ok else 503)


# Max PDF size for client uploads (100 MiB)
_MAX_PDF_BYTES = 100 * 1024 * 1024
_PDF_CONTENT_TYPES = ("application/pdf", "application/x-pdf", "application/octet-stream")


class UploadCompleteRequest(BaseModel):
    filename: str
    blobUrl: str


@app.post("/blob-upload")
def blob_upload(body: dict[str, Any]):
    """
    Vercel Blob handleUpload-compatible endpoint (@vercel/blob client upload()).
    """
    token = settings.blob_read_write_token.strip()
    if not token:
        raise HTTPException(
            status_code=503,
            detail="BLOB_READ_WRITE_TOKEN is not configured; cannot mint client tokens.",
        )

    event_type = body.get("type")
    if event_type == "blob.upload-completed":
        raise HTTPException(
            status_code=400,
            detail="Upload completion callbacks are not enabled; indexing is triggered via POST /upload-complete.",
        )

    if event_type != "blob.generate-client-token":
        raise HTTPException(status_code=400, detail=f"Unsupported event type: {event_type!r}")

    payload = body.get("payload") or {}
    pathname = payload.get("pathname")
    if not pathname or not isinstance(pathname, str):
        raise HTTPException(status_code=400, detail="Missing payload.pathname")

    one_hour_ms = 60 * 60 * 1000
    valid_until = int(time.time() * 1000) + one_hour_ms

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


@app.post("/upload-complete")
def upload_complete(
    req: UploadCompleteRequest,
    background_tasks: BackgroundTasks,
    indexing: IngestionPipeline = Depends(get_indexing),
):
    background_tasks.add_task(indexing.index_document, req.filename, req.blobUrl)
    return {"status": "upload recorded, indexing in progress"}


@app.get("/search")
def search(
    q: str = Query(...),
    top_k: int = Query(5, ge=1, le=50),
    es: ElasticsearchSearchBackend = Depends(get_search),
    embeddings: TextEncoder = Depends(get_embeddings),
):
    try:
        vector = embeddings.encode(q)
        results = es.hybrid_search(q, vector, top_k)
        for r in results:
            r["url"] = f"/files/{r['filename']}"
        return {"query": q, "total": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
def list_documents(search: ElasticsearchSearchBackend = Depends(get_search)):
    try:
        docs = search.list_documents()
        return {"total": len(docs), "documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/files/{filename}")
def delete_file(
    filename: str,
    es: ElasticsearchSearchBackend = Depends(get_search),
):
    try:
        es.delete_page(filename)
        return {"deleted": filename}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
