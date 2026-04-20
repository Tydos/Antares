import logging

from google import genai
from google.genai import types

from src.config import settings


_SYSTEM_INSTRUCTION = (
    "You are a retrieval-augmented assistant answering questions about the user's PDFs. "
    "Answer strictly from the provided context. If the answer is not in the context, "
    "say you don't know. Cite sources inline as [filename p.N] where N is the page number. "
    "Keep answers concise and faithful to the source material."
)

_NO_CONTEXT_ANSWER = "I couldn't find anything relevant in the indexed documents."

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        key = settings.gemini_api_key.strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        _client = genai.Client(api_key=key)
    return _client


def _format_chunks_as_context(chunks: list[dict]) -> str:
    blocks: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        header = f"[{i}] [{chunk.get('filename', 'unknown')} p.{chunk.get('page', '?')}]"
        blocks.append(f"{header}\n{chunk.get('content', '').strip()}")
    return "\n\n".join(blocks)


def generate_answer(question: str, chunks: list[dict]) -> str:
    """Ask Gemini to answer the question using only the retrieved chunks as context."""
    if not chunks:
        return _NO_CONTEXT_ANSWER

    client = _get_client()
    context = _format_chunks_as_context(chunks)
    prompt = (
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the context above. Cite sources as [filename p.N]."
    )

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            temperature=0.2,
        ),
    )

    text = (response.text or "").strip()
    if not text:
        logging.warning("Gemini returned an empty response")
        return _NO_CONTEXT_ANSWER
    return text
