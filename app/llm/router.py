import logging

from app.config.settings import settings

from app.llm.groq import GroqProvider
from app.llm.openrouter import OpenRouterProvider
from app.llm.gemini import GeminiProvider
from app.llm.openai import OpenAIProvider

from app.llm.exceptions import (
    LLMConfigurationError,
    LLMRateLimitError,
    LLMTemporaryError,
    LLMAuthenticationError,
    LLMProviderError,
)


logger = logging.getLogger(__name__)


class LLMRouter:

    def __init__(self):
        self.providers = {
            "groq": GroqProvider,
            "openrouter": OpenRouterProvider,
            "gemini": GeminiProvider,
            "openai": OpenAIProvider,
        }

        self.provider_order = [
            settings.primary_llm,
            settings.fallback_llm_1,
            settings.fallback_llm_2,
            settings.fallback_llm_3,
        ]

    def get_provider(self, provider_name: str):

        provider_name = provider_name.lower()

        if provider_name not in self.providers:
            raise ValueError(
                f"Unsupported LLM provider: {provider_name}"
            )

        return self.providers[provider_name]()

    def get_llm(self, provider_name: str):
        provider = self.get_provider(provider_name)
        return provider.get_llm()

    def get_primary_llm(self):
        return self.get_llm(settings.primary_llm)

    def _classify_error(self, error: Exception) -> Exception:

        status_code = getattr(error, "status_code", None)

        if status_code == 401:
            return LLMAuthenticationError(str(error))

        if status_code == 403:
            return LLMAuthenticationError(str(error))

        if status_code == 429:
            return LLMRateLimitError(str(error))

        if status_code in (500, 502, 503, 504):
            return LLMTemporaryError(str(error))

        return LLMProviderError(str(error))

    def invoke(self, messages):

        errors = []

        for provider_name in self.provider_order:

            try:
                logger.info(
                    "Trying LLM provider: %s",
                    provider_name
                )

                llm = self.get_llm(provider_name)

                response = llm.invoke(messages)

                logger.info(
                    "LLM provider succeeded: %s",
                    provider_name
                )

                return response

            except LLMConfigurationError as error:

                logger.warning(
                    "Skipping %s: %s",
                    provider_name,
                    error
                )

                errors.append(
                    f"{provider_name}: not configured"
                )

                continue

            except Exception as error:

                classified_error = self._classify_error(error)

                logger.warning(
                    "Provider %s failed: %s",
                    provider_name,
                    classified_error
                )

                errors.append(
                    f"{provider_name}: "
                    f"{type(classified_error).__name__}"
                )

                continue

        raise RuntimeError(
            "All configured LLM providers failed. "
            f"Errors: {errors}"
        )

    def get_structured_llm(self, schema):

        errors = []

        for provider_name in self.provider_order:

            try:
                logger.info(
                    "Trying structured LLM provider: %s",
                    provider_name
                )

                llm = self.get_llm(provider_name)

                structured_llm = llm.with_structured_output(
                    schema
                )

                return structured_llm

            except LLMConfigurationError as error:

                logger.warning(
                    "Skipping %s: %s",
                    provider_name,
                    error
                )

                errors.append(
                    f"{provider_name}: not configured"
                )

                continue

            except Exception as error:

                logger.warning(
                    "Provider %s failed: %s",
                    provider_name,
                    error
                )

                errors.append(
                    f"{provider_name}: {type(error).__name__}"
                )

                continue

        raise RuntimeError(
            "No LLM provider is available for structured output. "
            f"Errors: {errors}"
        )