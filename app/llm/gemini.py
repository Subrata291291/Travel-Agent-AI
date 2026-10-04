from langchain_google_genai import ChatGoogleGenerativeAI

from app.config.settings import settings
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import LLMConfigurationError


class GeminiProvider(BaseLLMProvider):

    def __init__(self):
        if not settings.google_api_key:
            raise LLMConfigurationError(
                "GOOGLE_API_KEY is not configured."
            )

        self.llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            temperature=0,
            google_api_key=settings.google_api_key,
        )

    def get_llm(self):
        return self.llm