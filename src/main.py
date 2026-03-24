import src.logger  # noqa: F401 — configures root logger before anything else

from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, Depends, FastAPI, File, Query, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from src.storage import MinioStorageBackend
from src.search import ElasticsearchSearchBackend
from src.indexing import IndexingService
from src.setup import init_services, get_storage, get_search, get_indexing


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — build all clients and backends before accepting requests
    services = init_services()
    app.state.storage = services["storage"]
    app.state.search  = services["search"]
    app.state.indexing = services["indexing"]
    yield
    
app = FastAPI(title="RAG PDF Hybrid Search", lifespan=lifespan)


@app.get("/")
def home():
    return {"message": "FastAPI server running"}


@app.get("/health")
def health(
    storage: MinioStorageBackend = Depends(get_storage),
    search: ElasticsearchSearchBackend = Depends(get_search),
):
    checks = {"minio": storage.ping(), "elasticsearch": search.ping()}
    ok = all(checks.values())
    return JSONResponse({"status": "ok" if ok else "degraded", "services": checks}, status_code=200 if ok else 503)


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Attach a PDF file"),
    storage: MinioStorageBackend = Depends(get_storage),
    indexing: IndexingService = Depends(get_indexing)
):
    try:
        url = await storage.upload(file)
        background_tasks.add_task(indexing.index_document, file.filename or "", url)
        return {"url": url, "status": "upload successful, indexing in progress"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search")
def search(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(5, ge=1, le=50, description="Number of results to return"),
    search: ElasticsearchSearchBackend = Depends(get_search),
):
    """Keyword search across all indexed PDF pages."""
    try:
        results = search.keyword_search(q, top_k)
        return {"query": q, "total": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
def list_documents(
    search: ElasticsearchSearchBackend = Depends(get_search),
):
    """List all indexed documents with page count and upload time."""
    try:
        docs = search.list_documents()
        return {"total": len(docs), "documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
