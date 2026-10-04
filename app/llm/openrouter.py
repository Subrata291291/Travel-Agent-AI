from langchain_openai import ChatOpenAI

from app.config.settings import settings
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import LLMConfigurationError


class OpenRouterProvider(BaseLLMProvider):

    def __init__(self):
        if not settings.openrouter_api_key:
            raise LLMConfigurationError(
                "OPENROUTER_API_KEY is not configured."
            )

        self.llm = ChatOpenAI(
            model=settings.openrouter_model,
            temperature=0,
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    def get_llm(self):
        return self.llm