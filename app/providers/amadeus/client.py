"""Small synchronous Amadeus Self-Service client for hotel search only."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import time
from typing import Any

import httpx

from app.config.settings import settings
from app.providers.errors import ProviderNotConfiguredError, ProviderRequestError


class AmadeusClient:
    TOKEN_PATH = "/v1/security/oauth2/token"

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
        max_attempts: int = 3,
    ) -> None:
        self.client_id = settings.amadeus_client_id if client_id is None else client_id
        self.client_secret = (
            settings.amadeus_client_secret if client_secret is None else client_secret
        )
        self.base_url = (base_url or settings.amadeus_base_url).rstrip("/")
        self.transport = transport
        self.sleep = sleep
        self.clock = clock
        self.max_attempts = max_attempts
        self.timeout = httpx.Timeout(20.0, connect=5.0)
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id.strip() and self.client_secret.strip())

    def _require_credentials(self) -> None:
        if not self.is_configured:
            raise ProviderNotConfiguredError(
                "Amadeus hotel search is disabled because client credentials are not configured."
            )
        if not self.base_url.startswith("https://"):
            raise ProviderRequestError("Amadeus base URL must use HTTPS.")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After", "")
        try:
            delay = float(value)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                delay = (retry_at - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                delay = 0.25 * (2 ** (attempt - 1))
        return min(max(delay, 0.0), 3.0)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._require_credentials()
        retryable_statuses = {429, 500, 502, 503, 504}

        for attempt in range(1, self.max_attempts + 1):
            try:
                with httpx.Client(
                    timeout=self.timeout,
                    transport=self.transport,
                ) as client:
                    response = client.request(
                        method,
                        f"{self.base_url}{path}",
                        params=params,
                        data=data,
                        headers=headers,
                    )
            except httpx.TimeoutException:
                if attempt >= self.max_attempts:
                    raise ProviderRequestError(
                        "Amadeus request timed out."
                    ) from None
                self.sleep(min(0.25 * (2 ** (attempt - 1)), 3.0))
                continue
            except httpx.RequestError:
                if attempt >= self.max_attempts:
                    raise ProviderRequestError(
                        "Unable to connect to Amadeus."
                    ) from None
                self.sleep(min(0.25 * (2 ** (attempt - 1)), 3.0))
                continue

            if response.status_code in retryable_statuses:
                if attempt >= self.max_attempts:
                    raise ProviderRequestError(
                        f"Amadeus request failed with HTTP {response.status_code}.",
                        response.status_code,
                    )
                self.sleep(self._retry_delay(response, attempt))
                continue

            if not 200 <= response.status_code < 300:
                raise ProviderRequestError(
                    f"Amadeus request failed with HTTP {response.status_code}.",
                    response.status_code,
                )

            try:
                result = response.json()
            except ValueError:
                raise ProviderRequestError(
                    "Amadeus returned an invalid JSON response.",
                    response.status_code,
                ) from None
            if not isinstance(result, dict):
                raise ProviderRequestError("Amadeus returned an invalid response.")
            return result

        raise ProviderRequestError("Amadeus request could not be completed.")

    def _token(self) -> str:
        self._require_credentials()
        if self._access_token and self.clock() < self._token_expires_at:
            return self._access_token

        response = self._request(
            "POST",
            self.TOKEN_PATH,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        access_token = response.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ProviderRequestError("Amadeus returned no access token.")
        try:
            lifetime = max(0, int(response.get("expires_in", 1800)))
        except (TypeError, ValueError):
            lifetime = 1800
        self._access_token = access_token
        self._token_expires_at = self.clock() + max(1, lifetime - 30)
        return access_token

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "GET",
            path,
            params=params,
            headers={"Authorization": f"Bearer {self._token()}"},
        )
