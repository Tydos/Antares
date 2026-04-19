import numpy as np
from huggingface_hub import InferenceClient

from src.config import settings


def _embedding_to_vector(arr) -> list[float]:
    """Turn HF feature_extraction output into one float vector per text."""
    a = np.asarray(arr, dtype=np.float64)
    if a.ndim == 2:
        return (a[0] if a.shape[0] == 1 else np.mean(a, axis=0)).tolist()
    return a.tolist()


class TextEncoder:
    """Embeddings via Hugging Face Inference (InferenceClient — not the legacy REST host)."""

    def __init__(
        self,
        model_id: str | None = None,
        dims: int | None = None,
    ) -> None:
        self._token = (settings.huggingface_api_token or "").strip()
        mid = model_id or settings.embedding_model
        # Optional full model URL; otherwise Hub model id (routes via Inference Providers).
        override = (settings.huggingface_inference_url or "").strip()
        model_ref = override or mid
        self._client = InferenceClient(
            model=model_ref,
            token=self._token or None,
            timeout=120.0,
        )
        self.dims = dims if dims is not None else settings.embedding_dims

    def _call(self, texts: list[str]) -> list[list[float]]:
        if not self._token:
            raise ValueError("Set HUGGINGFACE_API_TOKEN in the environment.")
        rows: list[list[float]] = []
        for t in texts:
            out = self._client.feature_extraction(t)
            rows.append(_embedding_to_vector(out))
        return rows

    def encode(self, text: str | list[str]) -> list[float] | list[list[float]]:
        if isinstance(text, str):
            return self._call([text])[0]
        if not text:
            return []
        out: list[list[float]] = []
        bs = settings.batch_size
        for i in range(0, len(text), bs):
            out.extend(self._call(text[i : i + bs]))
        return out
