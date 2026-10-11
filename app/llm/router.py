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

    def invoke_with_tools(self, messages, tools):
        """
        Try each configured LLM provider with tool calling.

        If the current provider fails, for example because of
        rate limits (429), authentication problems, or temporary
        provider errors, automatically try the next provider.
        """

        errors = []

        for provider_name in self.provider_order:
            try:
                logger.info(
                    "Trying tool-enabled LLM provider: %s",
                    provider_name,
                )

                llm = self.get_llm(provider_name)

                # Attach the tools to the current provider.
                tool_enabled_llm = llm.bind_tools(tools)

                # Invoke the current provider.
                response = tool_enabled_llm.invoke(messages)

                logger.info(
                    "Tool-enabled LLM provider succeeded: %s",
                    provider_name,
                )

                return response

            except LLMConfigurationError as error:
                logger.warning(
                    "Skipping %s: %s",
                    provider_name,
                    error,
                )

                errors.append(
                    f"{provider_name}: not configured"
                )

                continue

            except Exception as error:
                classified_error = self._classify_error(error)

                logger.warning(
                    "Tool-enabled provider %s failed: %s",
                    provider_name,
                    classified_error,
                )

                errors.append(
                    f"{provider_name}: "
                    f"{type(classified_error).__name__}"
                )

                continue

        raise RuntimeError(
            "All configured tool-enabled LLM providers failed. "
            f"Errors: {errors}"
        )

    def invoke_structured(self, prompt, schema):
        """
        Invoke a structured-output LLM with automatic provider fallback.

        This method is used when the application needs the LLM
        to return data matching a Pydantic schema.

        Example:
            TripPerception

        If one provider fails because of authentication,
        rate limiting, temporary errors, or another provider
        failure, the next configured provider is tried.
        """

        # Groq's JSON-object response mode requires the prompt to mention JSON.
        # Add the instruction only when the caller has not already done so.
        if isinstance(prompt, str) and "json" not in prompt.casefold():
            prompt = f"{prompt}\n\nReturn only JSON matching the requested schema."

        errors = []

        for provider_name in self.provider_order:
            try:
                logger.info(
                    "Trying structured LLM provider: %s",
                    provider_name,
                )

                # Create the current provider.
                llm = self.get_llm(provider_name)

                # Convert the LLM into a structured-output LLM.
                structured_llm = llm.with_structured_output(
                    schema,
                    method="json_mode",
                )

                # Invoke the structured model.
                response = structured_llm.invoke(prompt)

                if isinstance(response, schema):
                    validated_response = response
                else:
                    # Validate inside the provider loop so malformed output
                    # falls through to the next provider.
                    validated_response = schema.model_validate(response)

                logger.info(
                    "Structured LLM provider succeeded: %s",
                    provider_name,
                )

                return validated_response

            except LLMConfigurationError as error:
                logger.warning(
                    "Skipping %s: %s",
                    provider_name,
                    error,
                )

                errors.append(
                    f"{provider_name}: not configured"
                )

                continue

            except Exception as error:
                classified_error = self._classify_error(error)

                logger.warning(
                    "Structured provider %s failed (%s)",
                    provider_name,
                    type(classified_error).__name__,
                )

                errors.append(
                    f"{provider_name}: "
                    f"{type(classified_error).__name__}"
                )

                continue

        raise RuntimeError(
            "All configured structured LLM providers failed. "
            f"Errors: {errors}"
        )
