from langchain_openai import ChatOpenAI

from app.config.settings import settings
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import LLMConfigurationError


class OpenAIProvider(BaseLLMProvider):

    def __init__(self):
        if not settings.openai_api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY is not configured."
            )

        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0,
            api_key=settings.openai_api_key,
        )

    def get_llm(self):
        return self.llm