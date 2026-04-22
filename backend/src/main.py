import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from src.config import settings
from src.interfaces import DatabaseProtocol, EmbedderProtocol, GeneratorProtocol
from src.schemas import ChatRequest, QueryRequest, UploadCompleteRequest
from src.inference.generator import HuggingFaceGenerator
from src.inference.embedding import HuggingFaceEmbeddingService
from src.storage.database import PostgreSQLStorageManager
from src.ingestion.service import IngestionService
from src.ingestion.pdf_parser import PDFParser
from src.ingestion.upload_token import BlobTokenError, create_client_upload_token
from src.utils.latency import LatencyTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
    stream=sys.stdout,
)

# --- App startup ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = PostgreSQLStorageManager.create()
    app.state.embedder = HuggingFaceEmbeddingService()
    app.state.generator = HuggingFaceGenerator()
    app.state.extractor = PDFParser()
    app.state.pipeline = IngestionService(app.state.db, app.state.embedder, app.state.extractor)
    yield


app = FastAPI(title="RAG PDF API", lifespan=lifespan)
router = APIRouter()


# --- Dependency helpers ---

def get_db(request: Request) -> DatabaseProtocol:
    return request.app.state.db


def get_embedder(request: Request) -> EmbedderProtocol:
    return request.app.state.embedder


def get_generator(request: Request) -> GeneratorProtocol:
    return request.app.state.generator


def get_pipeline(request: Request) -> IngestionService:
    return request.app.state.pipeline


# --- Routes ---

@router.get("/")
def root():
    return {"message": "RAG PDF API. Visit /docs for the interactive API explorer."}


@router.get("/health")
def health(db: PostgreSQLStorageManager = Depends(get_db)):
    db_ok = db.ping()
    return JSONResponse(
        {"status": "ok" if db_ok else "degraded", "services": {"database": db_ok}},
        status_code=200 if db_ok else 503,
    )


@router.post("/request_upload_token")
def blob_upload(body: dict[str, Any]):
    """Step 1 of the upload flow: browser asks for a signed token to upload directly to Vercel Blob."""
    try:
        return create_client_upload_token(
            body,
            settings.blob_read_write_token.strip(),
            allowed_content_types=list(set(settings.blob_allowed_content_types)),
            maximum_size_in_bytes=settings.blob_max_pdf_bytes,
        )
    except BlobTokenError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e


@router.post("/upload-complete")
def upload_complete(
    req: UploadCompleteRequest,
    background_tasks: BackgroundTasks,
    db: PostgreSQLStorageManager = Depends(get_db),
    pipeline: IngestionService = Depends(get_pipeline),
):
    """Step 2 of the upload flow: browser notifies us the PDF is in blob storage so we can index it."""
    db.add_upload(req.filename, req.blobUrl)
    background_tasks.add_task(pipeline.index_document, req.filename, req.blobUrl)
    return {"status": "upload recorded, indexing in progress"}


@router.get("/documents")
def list_documents(db: PostgreSQLStorageManager = Depends(get_db)):
    return {"documents": db.list_uploads()}


@router.post("/query")
def query(
    req: QueryRequest,
    db: DatabaseProtocol = Depends(get_db),
    embedder: EmbedderProtocol = Depends(get_embedder),
    generator: GeneratorProtocol = Depends(get_generator),
):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    top_k = max(1, min(req.top_k, 20))
    tracker = LatencyTracker()

    try:
        with tracker.measure("embed"):
            query_vector = embedder.embed([question])[0]
    except Exception as e:
        logging.exception("Embedding failed")
        raise HTTPException(status_code=503, detail=f"Embedding service error: {e}")

    with tracker.measure("search"):
        chunks = db.search_chunks(
            query_vector,
            query_text=question,
            k=top_k,
            filenames=req.filenames or None,
            search_mode=req.search_mode,
        )

    answer: str | None = None
    try:
        with tracker.measure("llm"):
            answer = generator.generate_answer(question, chunks)
    except Exception:
        logging.exception("Answer generation failed; returning raw chunks")

    latency = tracker.all()
    logging.info(
        "query latency — embed: %.0fms | search: %.0fms | llm: %.0fms | total: %.0fms | chunks: %d",
        latency.get("embed", 0), latency.get("search", 0), latency.get("llm", 0), latency.get("total", 0), len(chunks),
    )

    return {
        "question": question,
        "answer": answer,
        "chunks": chunks,
        "latency": latency,
    }


@router.get("/history")
def get_history(db: PostgreSQLStorageManager = Depends(get_db)):
    return {"messages": db.get_messages()}


@router.post("/chat")
def chat(
    req: ChatRequest,
    db: PostgreSQLStorageManager = Depends(get_db),
    embedder: EmbedderProtocol = Depends(get_embedder),
    generator: GeneratorProtocol = Depends(get_generator),
):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    top_k = max(1, min(req.top_k, 20))
    tracker = LatencyTracker()

    try:
        with tracker.measure("embed"):
            query_vector = embedder.embed([question])[0]
    except Exception as e:
        logging.exception("Embedding failed")
        raise HTTPException(status_code=503, detail=f"Embedding service error: {e}")

    with tracker.measure("search"):
        chunks = db.search_chunks(
            query_vector,
            query_text=question,
            k=top_k,
            filenames=req.filenames or None,
            search_mode=req.search_mode,
        )

    history = db.get_messages()

    answer: str | None = None
    try:
        with tracker.measure("llm"):
            answer = generator.generate_answer_with_history(question, chunks, history)
    except Exception:
        logging.exception("Answer generation failed; returning raw chunks")

    db.add_message("user", question)
    db.add_message("assistant", answer or "", chunks)

    latency = tracker.all()
    logging.info(
        "chat latency — embed: %.0fms | search: %.0fms | llm: %.0fms | total: %.0fms | chunks: %d",
        latency.get("embed", 0), latency.get("search", 0), latency.get("llm", 0), latency.get("total", 0), len(chunks),
    )

    return {
        "answer": answer,
        "chunks": chunks,
        "latency": latency,
    }


@router.delete("/files/{filename}")
def delete_file(filename: str, db: PostgreSQLStorageManager = Depends(get_db)):
    try:
        db.remove_upload(filename)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"deleted": filename}


app.include_router(router)
