from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""
    blob_read_write_token: str = ""

    hf_token: str = ""
    hf_embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embed_dim: int = 384

    hf_llm_model: str = "meta-llama/Llama-3.2-1B-Instruct:novita"


settings = Settings()
