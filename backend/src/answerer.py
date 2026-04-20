import logging

from huggingface_hub import InferenceClient

from src.config import settings

_client = InferenceClient(api_key=settings.hf_token)

_NO_CONTEXT_ANSWER = "I couldn't find anything relevant in the indexed documents."


def _format_chunks_as_context(chunks: list[dict]) -> str:
    blocks: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        header = f"[{i}] [{chunk.get('filename', 'unknown')} p.{chunk.get('page', '?')}]"
        blocks.append(f"{header}\n{chunk.get('content', '').strip()}")
    return "\n\n".join(blocks)


def generate_answer(question: str, chunks: list[dict]) -> str:
    if not chunks:
        return _NO_CONTEXT_ANSWER

    context = _format_chunks_as_context(chunks)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a retrieval-augmented assistant answering questions about the user's PDFs. "
                "Answer strictly from the provided context. If the answer is not in the context, "
                "say you don't know. Cite sources inline as [filename p.N] where N is the page number. "
                "Keep answers concise and faithful to the source material."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Context:\n{context}\n\n"
                f"Question: {question}\n\n"
                "Answer using only the context above. Cite sources as [filename p.N]."
            ),
        },
    ]

    completion = _client.chat.completions.create(
        model=settings.hf_llm_model,
        messages=messages,
        max_tokens=400,
        temperature=0.2,
    )

    text = completion.choices[0].message.content.strip()
    if not text:
        logging.warning("HuggingFace LLM returned an empty response")
        return _NO_CONTEXT_ANSWER
    return text
