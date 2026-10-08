from typing import Any

import httpx

from app.config.settings import settings


class DuffelAPIError(Exception):
    """
    Raised when Duffel returns an API-level error.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code


class DuffelClient:
    """
    Low-level HTTP client for the Duffel API.

    Responsibilities:
    - Store Duffel API configuration
    - Add authentication headers
    - Make HTTP requests
    - Handle common HTTP/API errors

    This class does NOT:
    - Search flights
    - Decide which flight the user wants
    - Perform booking logic
    - Interact with LangGraph
    """

    def __init__(self) -> None:
        if not settings.duffel_api_key:
            raise ValueError(
                "DUFFEL_API_KEY is not configured. "
                "Add it to the .env file."
            )

        self.base_url = settings.duffel_base_url.rstrip("/")
        self.api_version = settings.duffel_version

        self.headers = {
            "Authorization": f"Bearer {settings.duffel_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Duffel-Version": self.api_version,
        }

    # =========================================================
    # ASYNC METHODS
    # =========================================================

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Perform an asynchronous GET request.
        """

        return await self._request(
            method="GET",
            path=path,
            params=params,
        )

    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Perform an asynchronous POST request.
        """

        return await self._request(
            method="POST",
            path=path,
            json=json,
        )

    # =========================================================
    # SYNC METHODS
    # =========================================================

    def get_sync(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Perform a synchronous GET request.

        Used by the current LangChain ToolExecutor,
        which calls tool.invoke().
        """

        return self._request_sync(
            method="GET",
            path=path,
            params=params,
        )

    def post_sync(
        self,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Perform a synchronous POST request.

        Used by synchronous LangChain tools.
        """

        return self._request_sync(
            method="POST",
            path=path,
            json=json,
        )

    # =========================================================
    # ASYNC INTERNAL REQUEST
    # =========================================================

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute an asynchronous HTTP request.
        """

        url = f"{self.base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=json,
                )

        except httpx.RequestError as exc:
            raise DuffelAPIError(
                f"Unable to connect to Duffel: {exc}"
            ) from exc

        return self._process_response(response)

    # =========================================================
    # SYNC INTERNAL REQUEST
    # =========================================================

    def _request_sync(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a synchronous HTTP request.

        This is intentionally separate from the async path
        because our current LangGraph ToolExecutor uses
        synchronous tool.invoke().
        """

        url = f"{self.base_url}{path}"

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=json,
                )

        except httpx.RequestError as exc:
            raise DuffelAPIError(
                f"Unable to connect to Duffel: {exc}"
            ) from exc

        return self._process_response(response)

    # =========================================================
    # COMMON RESPONSE HANDLER
    # =========================================================

    @staticmethod
    def _process_response(
        response: httpx.Response,
    ) -> dict[str, Any]:
        """
        Process a Duffel HTTP response.

        Both sync and async requests use this method so that
        error handling stays consistent.
        """

        if 200 <= response.status_code < 300:
            try:
                return response.json()

            except ValueError as exc:
                raise DuffelAPIError(
                    "Duffel returned an invalid JSON response.",
                    response.status_code,
                ) from exc

        try:
            error_body = response.json()

        except ValueError:
            error_body = response.text

        raise DuffelAPIError(
            message=f"Duffel API request failed: {error_body}",
            status_code=response.status_code,
        )