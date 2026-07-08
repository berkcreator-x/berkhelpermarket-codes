from __future__ import annotations

import asyncio
import time

import httpx

from src.ai.prompt_builder import SYSTEM_PROMPT
from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)

_TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=90.0,
    write=10.0,
    pool=5.0,
)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0

_NO_RETRY_STATUSES = {400, 401, 403}


class ProxyAPIError(Exception):
    """Typed exception for all ProxyAPI failures."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client

    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=_TIMEOUT)

    return _http_client


class ProxyAPIClient:

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.proxyapi_api_key}",
            "Content-Type": "application/json",
        }

    def _build_body(
        self,
        user_prompt: str,
    ) -> dict:

        return {
            "model": settings.ai_model,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": 0.7,
            "max_tokens": 1500,
            "response_format": {
                "type": "json_object"
            },
        }

    async def generate(
        self,
        user_prompt: str,
    ) -> str:

        if not settings.proxyapi_api_key:
            raise ProxyAPIError("ProxyAPI API key is not configured.")

        url = (
            f"{settings.proxyapi_base_url.rstrip('/')}"
            "/chat/completions"
        )

        body = self._build_body(user_prompt)

        last_exc: ProxyAPIError | None = None

        for attempt in range(1, _MAX_RETRIES + 1):

            started = time.perf_counter()

            try:

                response = await _get_http_client().post(
                    url,
                    headers=self._headers(),
                    json=body,
                )

            except httpx.TimeoutException as exc:

                logger.warning(
                    "proxyapi_timeout",
                    attempt=attempt,
                    error=str(exc),
                )

                last_exc = ProxyAPIError(
                    "AI timeout."
                )

                await self._backoff(attempt)

                continue

            except httpx.RequestError as exc:

                logger.warning(
                    "proxyapi_network_error",
                    attempt=attempt,
                    error=str(exc),
                )

                last_exc = ProxyAPIError(
                    "Network error."
                )

                await self._backoff(attempt)

                continue

            duration_ms = int(
                (time.perf_counter() - started) * 1000
            )

            if response.status_code in _NO_RETRY_STATUSES:

                logger.error(
                    "proxyapi_client_error",
                    status=response.status_code,
                    attempt=attempt,
                )

                raise ProxyAPIError(
                    f"HTTP {response.status_code}",
                    status_code=response.status_code,
                )

            if response.status_code == 429:

                logger.warning(
                    "proxyapi_rate_limit",
                    attempt=attempt,
                )

                last_exc = ProxyAPIError(
                    "Rate limit exceeded.",
                    status_code=429,
                )

                await self._backoff(attempt)

                continue

            if response.status_code != 200:

                logger.warning(
                    "proxyapi_server_error",
                    status=response.status_code,
                    attempt=attempt,
                    preview=response.text[:300],
                )

                last_exc = ProxyAPIError(
                    f"HTTP {response.status_code}",
                    status_code=response.status_code,
                )

                await self._backoff(attempt)

                continue

            try:

                payload = response.json()

                choices = payload.get("choices")

                if not choices:
                    raise ValueError("Empty choices")

                message = choices[0].get("message")

                if not message:
                    raise ValueError("Missing message")

                content = message.get("content", "").strip()

            except Exception as exc:

                logger.error(
                    "proxyapi_invalid_response",
                    preview=response.text[:500],
                )

                raise ProxyAPIError(
                    "Invalid AI response."
                ) from exc

            if not content:

                logger.error(
                    "proxyapi_empty_content",
                )

                raise ProxyAPIError(
                    "AI returned empty content."
                )

            logger.info(
                "proxyapi_success",
                model=settings.ai_model,
                duration_ms=duration_ms,
                prompt_length=len(user_prompt),
                response_length=len(content),
                tokens=payload.get("usage", {}).get("total_tokens"),
            )

            return content

        logger.error(
            "proxyapi_all_retries_failed",
            retries=_MAX_RETRIES,
        )

        raise last_exc or ProxyAPIError(
            "AI unavailable."
        )

    @staticmethod
    async def _backoff(
        attempt: int,
    ) -> None:

        delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))

        await asyncio.sleep(delay)


proxyapi_client = ProxyAPIClient()
