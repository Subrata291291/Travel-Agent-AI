import time
import logging
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
                    started = time.perf_counter()
                    outcome = "success"
                    return func(*args, **kwargs)

                except Exception as exc:
                    outcome = "retryable_failure" if is_retryable_exception(exc) else "failure"

                    if not is_retryable_exception(exc):
                        raise

                    if attempt >= max_attempts:
                        raise

                finally:
                    from app.core.request_context import get_request_id
                    logging.getLogger(__name__).info(
                        "Operation duration request_id=%s operation=ResolverToolAttempt name=%s attempt=%d outcome=%s elapsed_ms=%.2f",
                        get_request_id() or "unavailable", func.__name__, attempt, outcome,
                        (time.perf_counter()-started)*1000,
                    )

                    time.sleep(current_delay)

                    current_delay *= backoff_multiplier
                    attempt += 1

        return wrapper

    return decorator
