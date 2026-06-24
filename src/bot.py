from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from src.config import settings
from src.handlers import get_main_router
from src.middlewares import DBSessionMiddleware, RateLimitMiddleware


def create_bot() -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(redis: Redis) -> Dispatcher:
    storage = RedisStorage(redis=redis)
    dispatcher = Dispatcher(storage=storage)

    dispatcher.update.middleware(RateLimitMiddleware(redis=redis))
    dispatcher.update.middleware(DBSessionMiddleware())

    dispatcher.include_router(get_main_router())
    return dispatcher
