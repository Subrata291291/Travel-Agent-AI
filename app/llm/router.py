import logging
import re
from uuid import uuid4

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
    StructuredLLMUnavailable,
)
from app.core.request_context import get_request_id


logger = logging.getLogger(__name__)


class LLMRouter:

    _RATE_LIMIT_HEADERS = {
        "retry-after", "x-ratelimit-limit-requests", "x-ratelimit-remaining-requests",
        "x-ratelimit-reset-requests", "x-ratelimit-limit-tokens",
        "x-ratelimit-remaining-tokens", "x-ratelimit-reset-tokens",
        "ratelimit-limit", "ratelimit-remaining", "ratelimit-reset",
    }
    _SAFE_ERROR_CODES = {
        "rate_limit_exceeded", "insufficient_quota", "server_error",
        "invalid_request_error", "authentication_error", "api_error",
        "context_length_exceeded", "model_not_found", "overloaded_error",
        "json_validate_failed",
    }

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
        logger.info("LLM provider fallback order: %s", " -> ".join(self.provider_order))

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

        status_code = self._status_code(error)

        if status_code == 401:
            return LLMAuthenticationError(str(error))

        if status_code == 403:
            return LLMAuthenticationError(str(error))

        if status_code == 429:
            return LLMRateLimitError(str(error))

        if status_code in (500, 502, 503, 504):
            return LLMTemporaryError(str(error))

        return LLMProviderError(str(error))

    @staticmethod
    def _status_code(error: Exception) -> int | None:
        """Read a numeric status without logging provider response contents."""
        for source in (error, getattr(error, "response", None)):
            if source is None:
                continue
            for attribute in ("status_code", "code"):
                value = getattr(source, attribute, None)
                if isinstance(value, int):
                    return value
        return None

    @classmethod
    def _safe_error_details(cls, error: Exception) -> str:
        status_code = cls._status_code(error)
        details = type(error).__name__
        return f"{details}, status={status_code}" if status_code is not None else details

    @staticmethod
    def _safe_identifier(value, fallback="unknown", limit=96) -> str | None:
        if not isinstance(value, str):
            return fallback
        value = value.strip()
        if not value or len(value) > limit or not re.fullmatch(r"[A-Za-z0-9_.:/-]+", value):
            return fallback
        if value.casefold().startswith(("sk-", "key-", "bearer-")):
            return fallback
        return value

    @classmethod
    def _safe_response_id(cls, value) -> str | None:
        value = cls._safe_identifier(value, fallback=None, limit=120)
        if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            return None
        if value.casefold().startswith(("sk-", "key-", "bearer-")):
            return None
        return value

    @classmethod
    def _configured_model(cls, provider_name: str) -> str:
        return cls._safe_identifier(getattr(settings, f"{provider_name}_model", None))

    @classmethod
    def _safe_provider_code(cls, error: Exception):
        code = getattr(error, "code", None)
        if isinstance(code, int):
            return code if 100 <= code <= 599 else None
        if isinstance(code, str) and code.casefold() in cls._SAFE_ERROR_CODES:
            return code.casefold()
        return None

    @staticmethod
    def _safe_metadata_value(value):
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?(?:ms|s|m)?", value.strip(), re.I):
            return value.strip()
        return None

    @classmethod
    def _failure_metadata(cls, error: Exception) -> dict:
        response = getattr(error, "response", None)
        safe_headers = {}
        headers = getattr(response, "headers", None)
        if headers is not None:
            try:
                for key, value in headers.items():
                    normalized_key = str(key).casefold()
                    if normalized_key in cls._RATE_LIMIT_HEADERS:
                        safe_value = cls._safe_metadata_value(value)
                        if safe_value is not None:
                            safe_headers[normalized_key] = safe_value
            except Exception:
                pass

        response_id = None
        for source in (error, response):
            if source is None:
                continue
            for attribute in ("request_id", "response_id", "id"):
                response_id = cls._safe_response_id(getattr(source, attribute, None))
                if response_id:
                    break
            if response_id:
                break
            source_headers = getattr(source, "headers", None)
            if source_headers is not None:
                for key in ("x-request-id", "request-id", "x-groq-id", "x-openrouter-request-id"):
                    try:
                        response_id = cls._safe_response_id(source_headers.get(key))
                    except Exception:
                        response_id = None
                    if response_id:
                        break
            if response_id:
                break

        finish_reason = None
        for source in (error, response):
            candidate = getattr(source, "finish_reason", None) if source is not None else None
            if isinstance(candidate, str) and candidate.casefold() in {
                "stop", "length", "tool_calls", "content_filter", "error",
                "max_tokens", "end_turn", "stop_sequence",
            }:
                finish_reason = candidate.casefold()
                break

        raw_output = getattr(error, "llm_output", None)
        return {
            "status_code": cls._status_code(error),
            "provider_error_type": cls._safe_identifier(type(error).__name__),
            "provider_error_code": cls._safe_provider_code(error),
            "rate_limit_metadata": safe_headers or None,
            "output_length": len(raw_output) if isinstance(raw_output, str) else None,
            "response_id": response_id,
            "finish_reason": finish_reason,
        }

    @staticmethod
    def _exception_category(error: Exception) -> str:
        name = type(error).__name__.casefold()
        status = LLMRouter._status_code(error)
        if status == 429:
            return "rate_limit"
        if status in (401, 403):
            return "authentication"
        if "outputparser" in name or "jsondecode" in name:
            return "output_parse"
        if "validation" in name:
            return "schema_validation"
        if status in (500, 502, 503, 504):
            return "provider_temporary"
        return "provider_error"

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
                    "Skipping %s (provider is not configured)",
                    provider_name,
                )

                errors.append(
                    f"{provider_name}: not configured"
                )

                continue

            except Exception as error:

                classified_error = self._classify_error(error)

                logger.warning(
                    "Provider %s failed (%s)",
                    provider_name,
                    self._safe_error_details(error),
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
                    "Skipping %s (provider is not configured)",
                    provider_name,
                )

                errors.append(
                    f"{provider_name}: not configured"
                )

                continue

            except Exception as error:

                logger.warning(
                    "Provider %s failed (%s)",
                    provider_name,
                    self._safe_error_details(error),
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
                    "Skipping %s (provider is not configured)",
                    provider_name,
                )

                errors.append(
                    f"{provider_name}: not configured"
                )

                continue

            except Exception as error:
                classified_error = self._classify_error(error)

                logger.warning(
                    "Tool-enabled provider %s failed (%s)",
                    provider_name,
                    self._safe_error_details(error),
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

        operation = self._safe_identifier(
            getattr(schema, "__name__", None), "structured_call"
        )
        correlation_id = get_request_id() or str(uuid4())

        for provider_name in self.provider_order:
            try:
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
                    "Structured provider succeeded operation=%s provider=%s model=%s request_id=%s",
                    operation,
                    provider_name,
                    self._configured_model(provider_name),
                    correlation_id,
                )

                return validated_response

            except LLMConfigurationError as error:
                logger.warning(
                    "Structured provider failed operation=%s provider=%s model=%s request_id=%s category=configuration provider_error_type=%s",
                    operation,
                    provider_name,
                    self._configured_model(provider_name),
                    correlation_id,
                    self._safe_identifier(type(error).__name__),
                )

                continue

            except Exception as error:
                logger.warning(
                    "Structured provider failed operation=%s provider=%s model=%s request_id=%s category=%s metadata=%s",
                    operation,
                    provider_name,
                    self._configured_model(provider_name),
                    correlation_id,
                    self._exception_category(error),
                    self._failure_metadata(error),
                )

                continue

        raise StructuredLLMUnavailable(operation)
