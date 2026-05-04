from huggingface_hub import InferenceClient

from src.inference.adapters.base import LLMAdapter


class HuggingFaceAdapter(LLMAdapter):
    def __init__(self, model: str, token: str) -> None:
        self._client = InferenceClient(api_key=token)
        self._model = model

    def generate(self, messages: list[dict], max_tokens: int, temperature: float) -> str:
        res = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return res.choices[0].message.content.strip()
