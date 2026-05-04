import anthropic

from src.inference.adapters.base import LLMAdapter


class ClaudeAdapter(LLMAdapter):
    def __init__(self, model: str, token: str) -> None:
        self._client = anthropic.Anthropic(api_key=token)
        self._model = model

    def generate(self, messages: list[dict], max_tokens: int, temperature: float) -> str:
        # Claude takes system as a top-level param; extract it from the messages list.
        system = ""
        filtered = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                filtered.append(m)

        res = self._client.messages.create(
            model=self._model,
            system=system,
            messages=filtered,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return res.content[0].text.strip() if res.content else ""
