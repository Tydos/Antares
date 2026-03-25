import src.logger  # noqa: F401
import logging

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
    services = init_services()
    app.state.storage  = services["storage"]
    app.state.search   = services["search"]
    app.state.indexing = services["indexing"]
    yield


app = FastAPI(title="RAG PDF Hybrid Search", lifespan=lifespan)


@app.get("/")
def root():
    return {"message": "Welcome to the RAG PDF Hybrid Search API. Use /docs for interactive API docs."}

@app.get("/health")
def health(minio: MinioStorageBackend = Depends(get_storage), search: ElasticsearchSearchBackend = Depends(get_search)):
    checks = {"minio": minio.ping(), "elasticsearch": search.ping()}
    ok = all(checks.values())
    return JSONResponse({"status": "ok" if ok else "degraded", "services": checks}, status_code=200 if ok else 503)


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    minio: MinioStorageBackend = Depends(get_storage),
    indexing: IndexingService = Depends(get_indexing),
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
):
    try:
        results = es.keyword_search(q, top_k)
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
        es.delete_document_pages(filename)
        return {"deleted": filename}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
