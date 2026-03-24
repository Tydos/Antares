from minio import Minio
from elasticsearch import Elasticsearch
from fastapi import Request
from config import settings
from src.storage import MinioStorageBackend
from src.search import ElasticsearchSearchBackend
from src.indexing import IndexingService
import logging


def init_services() -> dict:
    """Build and return all backend instances. Called once at startup."""
    logging.info("Initialising storage backend...")
    storage = MinioStorageBackend(
        Minio(
            settings.minio_host,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure
        ),
        settings.bucket_name
    )

    logging.info("Initialising search backend...")
    search = ElasticsearchSearchBackend(
        Elasticsearch(settings.es_host),
        settings.index_name
    )

    return {
        "storage": storage,
        "search": search,
        "indexing": IndexingService(storage, search)
    }


# FastAPI Depends() factories — read pre-built instances from app.state
def get_storage(request: Request) -> MinioStorageBackend:
    return request.app.state.storage


def get_search(request: Request) -> ElasticsearchSearchBackend:
    return request.app.state.search


def get_indexing(request: Request) -> IndexingService:
    return request.app.state.indexing
