import time
from functools import wraps

import requests


RETRYABLE_STATUS_CODES = {
    429,
    500,
    502,
    503,
    504,
}


def is_retryable_exception(exc: Exception) -> bool:
    """
    Determine whether an exception represents
    a temporary failure that is safe to retry.
    """

    if isinstance(
        exc,
        (
            TimeoutError,
            ConnectionError,
            requests.Timeout,
            requests.ConnectionError,
        ),
    ):
        return True

    if isinstance(exc, requests.HTTPError):
        response = exc.response

        if response is not None:
            return response.status_code in RETRYABLE_STATUS_CODES

    return False


def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
):
    """
    Retry a function when a temporary failure occurs.

    max_attempts includes the first attempt.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    if delay_seconds < 0:
        raise ValueError("delay_seconds cannot be negative")

    if backoff_multiplier < 1:
        raise ValueError("backoff_multiplier must be at least 1")

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            attempt = 1
            current_delay = delay_seconds

            while True:

                try:
                    return func(*args, **kwargs)

                except Exception as exc:

                    if not is_retryable_exception(exc):
                        raise

                    if attempt >= max_attempts:
                        raise

                    time.sleep(current_delay)

                    current_delay *= backoff_multiplier
                    attempt += 1

        return wrapper

    return decorator