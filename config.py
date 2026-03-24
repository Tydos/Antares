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

    # Elasticsearch
    es_host: str = "http://elasticsearch:9200"
    index_name: str = "pdf-index"

    # Gemini (reserved for LLM step)
    gemini_api_key: str = ""


settings = Settings()