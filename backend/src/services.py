from fastapi import FastAPI, Request

from src.document_store import DocumentStore, create_pool
from src.ingestion import IngestionPipeline


def init_services(app: FastAPI) -> None:
    pool = create_pool()
    app.state.store = DocumentStore(pool)
    app.state.indexing = IngestionPipeline(app.state.store)


def get_store(request: Request) -> DocumentStore:
    return request.app.state.store


def get_indexing(request: Request) -> IngestionPipeline:
    return request.app.state.indexing
