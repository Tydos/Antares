import httpx

from src.config import settings

_HF_URL = (
    f"https://router.huggingface.co/hf-inference/models/"
    f"{settings.hf_embed_model}/pipeline/feature-extraction"
)


def _embed_batch(texts: list[str]) -> list[list[float]]:
    response = httpx.post(
        _HF_URL,
        headers={"Authorization": f"Bearer {settings.hf_token}"},
        json={"inputs": texts, "options": {"wait_for_model": True}},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    # Single-text requests return a flat list; wrap it so the shape is always list[list[float]]
    if isinstance(data, list) and data and not isinstance(data[0], list):
        data = [data]
    return data


def embed(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Return one embedding vector per text, fetched from the HuggingFace Inference API."""
    if not texts:
        return []
    if not settings.hf_token:
        raise RuntimeError("HF_TOKEN is not configured.")

    results: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        results.extend(_embed_batch(texts[i : i + batch_size]))
    return results
