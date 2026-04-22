import httpx
from src.config import settings

class HuggingFaceEmbeddingService:
    def __init__(self) -> None:
        self._url = (
            f"https://router.huggingface.co/hf-inference/models/"
            f"{settings.hf_embed_model}/pipeline/feature-extraction"
        )

    def _fetch_embeddings(self, texts: list[str]) -> list[list[float]]:
        response = httpx.post(
            self._url,
            headers={"Authorization": f"Bearer {settings.hf_token}"},
            json={"inputs": texts, "options": {"wait_for_model": True}},
            timeout=settings.hf_embed_timeout,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data and not isinstance(data[0], list):
            data = [data]
        return data

    def embed(self, texts: list[str], batch_size: int | None = None) -> list[list[float]]:
        if not texts:
            return []
        if not settings.hf_token:
            raise RuntimeError("HF_TOKEN is not configured.")
        size = batch_size or settings.hf_embed_batch_size
        results: list[list[float]] = []
        for i in range(0, len(texts), size):
            results.extend(self._fetch_embeddings(texts[i : i + size]))
        return results
