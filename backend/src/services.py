from minio import Minio
from elasticsearch import Elasticsearch
from fastapi import Request
from src.config import settings
from src.backends.storage import MinioStorageBackend
from src.backends.search import ElasticsearchSearchBackend
from src.pipeline.ingestion import IngestionPipeline
from src.backends.embeddings import TextEncoder
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

    logging.info("Initialising embedding service...")
    embeddings = TextEncoder()

    return {
        "storage": storage,
        "search": search,
        "embeddings": embeddings,
        "indexing": IngestionPipeline(storage, search, embeddings)
    }


# FastAPI Depends() factories — read pre-built instances from app.state
def get_storage(request: Request) -> MinioStorageBackend:
    return request.app.state.storage


def get_search(request: Request) -> ElasticsearchSearchBackend:
    return request.app.state.search


def get_indexing(request: Request) -> IngestionPipeline:
    return request.app.state.indexing


def get_embeddings(request: Request) -> TextEncoder:
    return request.app.state.embeddings
