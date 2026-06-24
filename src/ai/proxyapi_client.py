from __future__ import annotations

import asyncio
import time

import httpx

from src.ai.prompt_builder import SYSTEM_PROMPT
from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)

# Таймауты: 10 сек на соединение, 90 сек на чтение ответа модели
_TIMEOUT = httpx.Timeout(connect=10.0, read=90.0, write=10.0, pool=5.0)

# Retry: 3 попытки с экспоненциальным backoff (1s → 2s → 4s)
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0

# Статусы, при которых не нужен повтор запроса (клиентские ошибки)
_NO_RETRY_STATUSES = {400, 401, 403}


class ProxyAPIError(Exception):
    """Typed exception for all ProxyAPI / AI failures."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# Singleton async httpx client — переиспользуется между запросами (connection pooling).
# Создаётся лениво при первом вызове generate().
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=_TIMEOUT)
    return _http_client


class ProxyAPIClient:
    """Async client for ProxyAPI (OpenAI-compatible) with exponential backoff retry.

    Stateless: конфигурация читается из settings при каждом вызове.
    Безопасен для stateless-окружений (Render, Docker).
    """

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.proxyapi_api_key}",
            "Content-Type": "application/json",
        }

    def _build_body(self, user_prompt: str) -> dict:
        return {
            "model": settings.ai_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1500,
        }

    async def generate(self, user_prompt: str) -> str:
        """Отправить запрос к ProxyAPI и вернуть текстовый ответ модели.

        Выполняет до _MAX_RETRIES попыток с экспоненциальным backoff.
        При ошибках клиента (401, 403, 400) — не повторяет.
        """
        url = f"{settings.proxyapi_base_url.rstrip('/')}/chat/completions"
        body = self._build_body(user_prompt)
        last_exc: ProxyAPIError | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            t_start = time.monotonic()
            try:
                client = _get_http_client()
                response = await client.post(url, headers=self._headers(), json=body)
            except httpx.TimeoutException as exc:
                elapsed = round(time.monotonic() - t_start, 2)
                logger.warning(
                    "proxyapi_timeout",
                    attempt=attempt,
                    elapsed_sec=elapsed,
                    error=str(exc),
                )
                last_exc = ProxyAPIError("Превышено время ожидания ответа от AI-сервиса")
                await self._backoff(attempt)
                continue
            except httpx.RequestError as exc:
                elapsed = round(time.monotonic() - t_start, 2)
                logger.warning(
                    "proxyapi_network_error",
                    attempt=attempt,
                    elapsed_sec=elapsed,
                    error=str(exc),
                )
                last_exc = ProxyAPIError("Сетевая ошибка при обращении к AI-сервису")
                await self._backoff(attempt)
                continue

            elapsed = round(time.monotonic() - t_start, 2)

            if response.status_code in _NO_RETRY_STATUSES:
                logger.error(
                    "proxyapi_client_error",
                    status=response.status_code,
                    attempt=attempt,
                    elapsed_sec=elapsed,
                )
                raise ProxyAPIError(
                    f"Ошибка авторизации или запроса к AI-сервису (HTTP {response.status_code})",
                    status_code=response.status_code,
                )

            if response.status_code == 429:
                logger.warning(
                    "proxyapi_rate_limit",
                    attempt=attempt,
                    elapsed_sec=elapsed,
                )
                last_exc = ProxyAPIError("Превышен лимит запросов к AI-сервису", status_code=429)
                await self._backoff(attempt)
                continue

            if response.status_code != 200:
                logger.warning(
                    "proxyapi_unexpected_status",
                    status=response.status_code,
                    attempt=attempt,
                    elapsed_sec=elapsed,
                    body_preview=response.text[:300],
                )
                last_exc = ProxyAPIError(
                    f"Неожиданный ответ AI-сервиса (HTTP {response.status_code})",
                    status_code=response.status_code,
                )
                await self._backoff(attempt)
                continue

            # Успешный ответ
            try:
                payload = response.json()
                content: str = payload["choices"][0]["message"]["content"]
            except (KeyError, IndexError, ValueError) as exc:
                logger.error(
                    "proxyapi_parse_error",
                    attempt=attempt,
                    response_preview=response.text[:300],
                )
                raise ProxyAPIError("Неожиданный формат ответа от AI-сервиса") from exc

            logger.info(
                "proxyapi_success",
                model=settings.ai_model,
                attempt=attempt,
                elapsed_sec=elapsed,
                tokens_used=payload.get("usage", {}).get("total_tokens"),
            )
            return content.strip()

        # Все попытки исчерпаны
        logger.error(
            "proxyapi_all_retries_failed",
            max_retries=_MAX_RETRIES,
            model=settings.ai_model,
        )
        raise last_exc or ProxyAPIError("AI-сервис недоступен после нескольких попыток")

    @staticmethod
    async def _backoff(attempt: int) -> None:
        """Exponential backoff: 1s, 2s, 4s, ..."""
        delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
        logger.debug("proxyapi_backoff", delay_sec=delay, attempt=attempt)
        await asyncio.sleep(delay)


proxyapi_client = ProxyAPIClient()
