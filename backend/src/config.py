from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""
    database_pool_min_size: int = 1
    database_pool_max_size: int = 10
    log_level: str = "INFO"
    query_top_k_max: int = 20

    blob_read_write_token: str = ""
    blob_token_ttl_ms: int = 60 * 60 * 1000
    blob_max_pdf_bytes: int = 100 * 1024 * 1024
    blob_allowed_content_types: list[str] = ["application/pdf", "application/x-pdf", "application/octet-stream"]

    hf_token: str = ""
    hf_embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embed_dim: int = 384

    pdf_chunk_size: int = 800
    pdf_chunk_overlap: int = 100

    hf_embed_batch_size: int = 32
    hf_embed_timeout: int = 60

    hf_llm_model: str = "meta-llama/Llama-3.2-1B-Instruct:novita"
    hf_llm_max_tokens: int = 400
    hf_llm_temperature: float = 0.2


settings = Settings()
