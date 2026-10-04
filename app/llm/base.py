from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):

    @abstractmethod
    def get_llm(self) -> Any:
        """Return the configured LLM instance."""
        raise NotImplementedError