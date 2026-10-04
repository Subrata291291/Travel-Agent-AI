from langchain_groq import ChatGroq

from app.config.settings import settings
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import LLMConfigurationError


class GroqProvider(BaseLLMProvider):

    def __init__(self):
        if not settings.groq_api_key:
            raise LLMConfigurationError(
                "GROQ_API_KEY is not configured."
            )

        self.llm = ChatGroq(
            model=settings.groq_model,
            temperature=0,
            api_key=settings.groq_api_key,
        )

    def get_llm(self):
        return self.llm