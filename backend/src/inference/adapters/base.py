from abc import ABC, abstractmethod


class LLMAdapter(ABC):
    @abstractmethod
    def generate(self, messages: list[dict], max_tokens: int, temperature: float) -> str:
        pass
