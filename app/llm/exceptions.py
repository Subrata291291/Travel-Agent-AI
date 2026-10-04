class LLMError(Exception):
    """Base exception for LLM-related errors."""


class LLMConfigurationError(LLMError):
    """Raised when a provider is not configured correctly."""


class LLMAuthenticationError(LLMError):
    """Raised when provider authentication fails."""


class LLMRateLimitError(LLMError):
    """Raised when a provider rate limit is reached."""


class LLMTemporaryError(LLMError):
    """Raised for temporary provider/server failures."""


class LLMProviderError(LLMError):
    """Raised for other provider failures."""