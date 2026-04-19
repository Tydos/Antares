from elasticsearch import Elasticsearch
from fastapi import Request
from src.config import settings
from src.backends.search import ElasticsearchSearchBackend
from src.pipeline.ingestion import IngestionPipeline
from src.backends.embeddings import TextEncoder
import logging


def init_services() -> dict:
    """Build and return all backend instances. Called once at startup."""
    logging.info("Initialising search backend...")
    search = ElasticsearchSearchBackend(
        Elasticsearch(settings.es_host),
        settings.index_name
    )

    logging.info("Initialising embedding service...")
    embeddings = TextEncoder()

    return {
        "search": search,
        "embeddings": embeddings,
        "indexing": IngestionPipeline(search, embeddings),
    }


# FastAPI Depends() factories — read pre-built instances from app.state
def get_search(request: Request) -> ElasticsearchSearchBackend:
    return request.app.state.search


def get_indexing(request: Request) -> IngestionPipeline:
    return request.app.state.indexing


def get_embeddings(request: Request) -> TextEncoder:
    return request.app.state.embeddings
