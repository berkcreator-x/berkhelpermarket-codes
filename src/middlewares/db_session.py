from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update

from src.database import AsyncSessionLocal
from src.utils import get_logger

logger = get_logger(__name__)


class DBSessionMiddleware(BaseMiddleware):
    """Создаёт SQLAlchemy AsyncSession для каждого обновления.

    Коммитит при успехе, откатывает и логирует при ошибке.
    Состояние не хранится между обновлениями (stateless).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with AsyncSessionLocal() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
            except Exception as exc:
                await session.rollback()
                logger.error(
                    "db_session_rollback",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                if isinstance(event, Update) and event.message is not None:
                    await event.message.answer("❌ Ошибка: " + str(exc))
                return None
            else:
                await session.commit()
                return result
