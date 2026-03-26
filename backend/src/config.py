from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # MinIO
    minio_host: str = "minio:9000"
    minio_access_key: str = "admin"
    minio_secret_key: str = "admin123"
    minio_secure: bool = False
    bucket_name: str = "pdf-files"
    upload_chunk_size: int = 10 * 1024 * 1024  # 10 MB

    # Elasticsearch
    es_host: str = "http://elasticsearch:9200"
    index_name: str = "pdf-index"

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dims: int = 384
    batch_size: int = 16
    

    # Gemini (reserved for LLM step)
    gemini_api_key: str = ""


settings = Settings()