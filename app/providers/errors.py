class ProviderNotConfiguredError(RuntimeError):
    """Raised when an optional provider has no usable integration config."""


class ProviderRequestError(RuntimeError):
    """Raised for a sanitized provider HTTP or response failure."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
