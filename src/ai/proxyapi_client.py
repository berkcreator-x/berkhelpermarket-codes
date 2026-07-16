from __future__ import annotations

import asyncio
import base64
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

# Генерация изображений может занимать до ~2 минут —
# отдельный, более длинный таймаут именно для неё.
_IMAGE_TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=170.0,
    write=30.0,
    pool=5.0,
)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.5

_NO_RETRY_STATUSES = {
    400,
    401,
    403,
}


class ProxyAPIError(Exception):
    """Typed exception for ProxyAPI."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


_http_client: httpx.AsyncClient | None = None
_image_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client

    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=_TIMEOUT)

    return _http_client


def _get_image_http_client() -> httpx.AsyncClient:
    global _image_http_client

    if (
        _image_http_client is None
        or _image_http_client.is_closed
    ):
        _image_http_client = httpx.AsyncClient(
            timeout=_IMAGE_TIMEOUT
        )

    return _image_http_client


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
            "temperature": 0.55,
            "max_tokens": 1300,
            "response_format": {
                "type": "json_object"
            },
        }

    async def generate(
        self,
        user_prompt: str,
    ) -> str:

        if not settings.proxyapi_api_key:
            raise ProxyAPIError(
                "ProxyAPI API key is not configured."
            )

        url = (
            f"{settings.proxyapi_base_url.rstrip('/')}"
            "/chat/completions"
        )

        body = self._build_body(user_prompt)

        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):

            started = time.perf_counter()

            try:

                response = await _get_http_client().post(
                    url,
                    headers=self._headers(),
                    json=body,
                )

            except Exception as exc:

                last_error = exc

                logger.warning(
                    "proxyapi_network_error",
                    attempt=attempt,
                    error=str(exc),
                )

                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(
                        _RETRY_BASE_DELAY * attempt
                    )
                    continue

                raise ProxyAPIError(
                    "AI unavailable."
                ) from exc

            elapsed = round(
                time.perf_counter() - started,
                2,
            )

            logger.info(
                "proxyapi_response",
                status=response.status_code,
                seconds=elapsed,
            )

            if response.status_code == 200:
                break

            logger.error(
                "proxyapi_failed",
                status=response.status_code,
                attempt=attempt,
                body=response.text[:400],
            )

            if response.status_code in _NO_RETRY_STATUSES:

                raise ProxyAPIError(
                    f"HTTP {response.status_code}",
                    response.status_code,
                )

            if attempt < _MAX_RETRIES:

                await asyncio.sleep(
                    _RETRY_BASE_DELAY * attempt
                )

                continue

            raise ProxyAPIError(
                f"HTTP {response.status_code}",
                response.status_code,
            )

        try:

            payload = response.json()

        except Exception as exc:

            logger.error(
                "proxyapi_invalid_json",
                body=response.text[:500],
            )

            raise ProxyAPIError(
                "Invalid JSON."
            ) from exc

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

        if not content:

            raise ProxyAPIError(
                "Empty AI response."
            )

        content = content.strip()

        if not content:

            raise ProxyAPIError(
                "Empty AI response."
            )

        return content

    async def edit_image(
        self,
        image_bytes: bytes,
        prompt: str,
        filename: str = "product.jpg",
        mime_type: str = "image/jpeg",
        size: str = "1024x1536",
        quality: str = "low",
        input_fidelity: str = "high",
    ) -> bytes:
        """
        Отправляет фото пользователя + текстовый промпт
        в /images/edits и возвращает готовое изображение
        как raw bytes (PNG).

        input_fidelity="high" — критично важный параметр:
        заставляет модель максимально точно сохранять
        детали исходного фото (логотип, форму, цвет товара)
        вместо творческой "фантазии". Не поддерживается
        моделью gpt-image-1-mini — поэтому используется
        gpt-image-1 (дороже, но реально сохраняет бренд).

        quality="low" по умолчанию — контроль себестоимости
        на время тестирования: input_fidelity и quality
        независимые параметры, есть гипотеза, что низкое
        quality не мешает высокой точности сохранения
        деталей товара. Требует проверки на реальном фото.
        """

        if not settings.proxyapi_api_key:
            raise ProxyAPIError(
                "ProxyAPI API key is not configured."
            )

        url = (
            f"{settings.proxyapi_base_url.rstrip('/')}"
            "/images/edits"
        )

        headers = {
            "Authorization": f"Bearer {settings.proxyapi_api_key}",
        }

        data = {
            "model": settings.ai_image_model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "input_fidelity": input_fidelity,
        }

        files = {
            "image[]": (
                filename,
                image_bytes,
                mime_type,
            ),
        }

        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):

            started = time.perf_counter()

            try:

                response = await _get_image_http_client().post(
                    url,
                    headers=headers,
                    data=data,
                    files=files,
                )

            except Exception as exc:

                last_error = exc

                logger.warning(
                    "proxyapi_image_network_error",
                    attempt=attempt,
                    error=str(exc),
                )

                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(
                        _RETRY_BASE_DELAY * attempt
                    )
                    continue

                raise ProxyAPIError(
                    "Image AI unavailable."
                ) from exc

            elapsed = round(
                time.perf_counter() - started,
                2,
            )

            logger.info(
                "proxyapi_image_response",
                status=response.status_code,
                seconds=elapsed,
            )

            if response.status_code == 200:
                break

            logger.error(
                "proxyapi_image_failed",
                status=response.status_code,
                attempt=attempt,
                body=response.text[:400],
            )

            if response.status_code in _NO_RETRY_STATUSES:

                raise ProxyAPIError(
                    f"HTTP {response.status_code}",
                    response.status_code,
                )

            if attempt < _MAX_RETRIES:

                await asyncio.sleep(
                    _RETRY_BASE_DELAY * attempt
                )

                continue

            raise ProxyAPIError(
                f"HTTP {response.status_code}",
                response.status_code,
            )

        try:

            payload = response.json()

        except Exception as exc:

            logger.error(
                "proxyapi_image_invalid_json",
                body=response.text[:500],
            )

            raise ProxyAPIError(
                "Invalid JSON."
            ) from exc

        try:

            b64_data = payload["data"][0]["b64_json"]

        except Exception as exc:

            logger.error(
                "proxyapi_image_invalid_response",
                body=str(payload)[:600],
            )

            raise ProxyAPIError(
                "Invalid image response."
            ) from exc

        if not b64_data:

            raise ProxyAPIError(
                "Empty image response."
            )

        try:
            return base64.b64decode(b64_data)
        except Exception as exc:
            raise ProxyAPIError(
                "Failed to decode image data."
            ) from exc


proxyapi_client = ProxyAPIClient()
