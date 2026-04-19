import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""
    blob_read_write_token: str = ""

    # Vercel Services: routePrefix (see vercel.json). Empty locally; /_/backend on Vercel.
    route_prefix: str = ""

    @model_validator(mode="after")
    def normalize_route_prefix(self) -> "Settings":
        rp = (self.route_prefix or "").strip()
        if not rp and os.environ.get("VERCEL"):
            rp = "/_/backend"
        if rp:
            rp = "/" + rp.strip("/")
        self.route_prefix = rp
        return self


settings = Settings()
