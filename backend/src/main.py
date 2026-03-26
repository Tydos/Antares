from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, Depends, FastAPI, Query, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
import src.utils.logger  # noqa: F401 — configures root logger as a side effect
from src.backends.storage import MinioStorageBackend
from src.backends.search import ElasticsearchSearchBackend
from src.pipeline.ingestion import IngestionPipeline
from src.services import init_services, get_storage, get_search, get_indexing, get_embeddings
from src.backends.embeddings import TextEncoder


@asynccontextmanager
async def lifespan(app: FastAPI):
    services = init_services()
    app.state.storage    = services["storage"]
    app.state.search     = services["search"]
    app.state.indexing   = services["indexing"]
    app.state.embeddings = services["embeddings"]
    yield


app = FastAPI(title="RAG PDF Hybrid Search", lifespan=lifespan)


@app.get("/")
def root():
    return {"message": "Welcome to the RAG PDF Hybrid Search API. Use /docs for interactive API docs."}

@app.get("/health")
def health(minio: MinioStorageBackend = Depends(get_storage), search: ElasticsearchSearchBackend = Depends(get_search)):
    checks = {"minio": minio.ping_minio(), "elasticsearch": search.ping_es()}
    ok = all(checks.values())
    return JSONResponse({"status": "ok" if ok else "degraded", "services": checks}, status_code=200 if ok else 503)


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    minio: MinioStorageBackend = Depends(get_storage),
    indexing: IngestionPipeline = Depends(get_indexing),
):
    try:
        filename = await minio.upload(file)
        background_tasks.add_task(indexing.index_document, filename)
        return {"url": f"/files/{filename}", "status": "upload successful, indexing in progress"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    minio: MinioStorageBackend = Depends(get_storage),
    es: ElasticsearchSearchBackend = Depends(get_search),
):
    try:
        minio.delete(filename)
        es.delete_page(filename)
        return {"deleted": filename}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
