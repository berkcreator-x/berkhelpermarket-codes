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

        try:

            response = await _get_http_client().post(
                url,
                headers=self._headers(),
                json=body,
            )

        except Exception as exc:

            raise ProxyAPIError(
                "AI unavailable."
            ) from exc

        if response.status_code != 200:

            logger.error(
                "proxyapi_failed",
                status=response.status_code,
                body=response.text[:400],
            )

            raise ProxyAPIError(
                f"HTTP {response.status_code}"
            )

        payload = response.json()

        try:

            content = payload["choices"][0]["message"]["content"]

        except Exception as exc:

            logger.error(
                "proxyapi_invalid_response",
                body=str(payload)[:600],
            )

            raise ProxyAPIError(
                "Invalid response."
            ) from exc

        return content.strip()


proxyapi_client = ProxyAPIClient()
