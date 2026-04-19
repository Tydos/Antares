from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Elasticsearch
    es_host: str = "http://elasticsearch:9200"
    index_name: str = "pdf-index"

    # Embeddings (Hugging Face Inference API — see backends/embeddings.py)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dims: int = 384
    batch_size: int = 16
    huggingface_api_token: str = ""
    # Optional: full inference URL or model id override (InferenceClient `model` argument)
    huggingface_inference_url: str = ""

    # Gemini (reserved for LLM step)
    gemini_api_key: str = ""

    # Vercel Blob (client uploads — mint tokens in FastAPI)
    blob_read_write_token: str = ""

    @field_validator("huggingface_api_token", "blob_read_write_token", mode="before")
    @classmethod
    def strip_secrets(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


settings = Settings()
