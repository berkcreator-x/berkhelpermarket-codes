from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from redis.asyncio import Redis

from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Simple sliding-window rate limiter backed by Redis.

    Limits each user to `settings.rate_limit_messages` updates per
    `settings.rate_limit_period_seconds`. Uses Redis INCR + EXPIRE, which is
    safe across multiple bot instances and survives process restarts.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._limit = settings.rate_limit_messages
        self._period = settings.rate_limit_period_seconds

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        if isinstance(event, Update):
            if event.message is not None and event.message.from_user is not None:
                user_id = event.message.from_user.id
            elif event.callback_query is not None and event.callback_query.from_user is not None:
                user_id = event.callback_query.from_user.id

        if user_id is None:
            return await handler(event, data)

        key = f"ratelimit:{user_id}"
        current = await self._redis.incr(key)
        if current == 1:
            await self._redis.expire(key, self._period)

        if current > self._limit:
            logger.warning("rate_limit_exceeded", user_id=user_id, current=current)
            if isinstance(event, Update) and event.message is not None:
                await event.message.answer("⏳ Слишком много запросов. Подождите немного и попробуйте снова.")
            elif isinstance(event, Update) and event.callback_query is not None:
                await event.callback_query.answer(
                    "⏳ Слишком много запросов. Подождите немного.", show_alert=True
                )
            return None

        return await handler(event, data)
