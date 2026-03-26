from sentence_transformers import SentenceTransformer
from src.config import settings


class TextEncoder:
    """Wrapper around SentenceTransformer.

    Parameters
    ----------
    model_name:   HuggingFace model id or local path.
    dims:         Expected output dimensionality — must match the ES mapping.
    normalize:    L2-normalise embeddings (required for cosine similarity).
    """

    def __init__(
        self,
        model_name: str = settings.embedding_model,
        dims: int       = settings.embedding_dims,
        normalize: bool = True,
    ) -> None:
        self._model     = SentenceTransformer(model_name)
        self._normalize = normalize
        self.dims       = dims

    def encode(self, text: str | list[str]) -> list[float] | list[list[float]]:
        return self._model.encode(
            text,
            normalize_embeddings=self._normalize,
            show_progress_bar=False,
        ).tolist()

