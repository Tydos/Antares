import logging
from huggingface_hub import InferenceClient
from src.config import settings

_NO_CONTEXT_ANSWER = "I couldn't find anything relevant in the indexed documents."

class HuggingFaceGenerator:
    def __init__(self) -> None:
        self._client = InferenceClient(api_key=settings.hf_token)

    def _format_chunks_as_context(self, chunks: list[dict]) -> str:
        blocks: list[str] = []
        for i, chunk in enumerate(chunks, start=1):
            page = chunk.get("page") or "?"
            header = f"[{i}] [{chunk.get('filename', 'unknown')} p.{page}]"
            blocks.append(f"{header}\n{chunk.get('content', '').strip()}")
        return "\n\n".join(blocks)

    def generate_answer_with_history(self, question: str, chunks: list[dict], history: list[dict]) -> str:
        if not chunks:
            return _NO_CONTEXT_ANSWER

        context = self._format_chunks_as_context(chunks)
        prior_turns = [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
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
            *prior_turns,
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\n"
                    f"Question: {question}\n\n"
                    "Answer using only the context above. Cite sources as [filename p.N]."
                ),
            },
        ]

        try:
            completion = self._client.chat.completions.create(
                model=settings.hf_llm_model,
                messages=messages,
                max_tokens=settings.hf_llm_max_tokens,
                temperature=settings.hf_llm_temperature,
            )
        except Exception:
            logging.exception("HuggingFace LLM inference failed")
            return _NO_CONTEXT_ANSWER

        text = completion.choices[0].message.content.strip()
        if not text:
            logging.warning("HuggingFace LLM returned an empty response")
            return _NO_CONTEXT_ANSWER
        return text

    def generate_answer(self, question: str, chunks: list[dict]) -> str:
        return self.generate_answer_with_history(question, chunks, [])
