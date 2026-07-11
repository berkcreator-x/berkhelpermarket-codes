from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories import UserRepository

router = Router(name="history")

HISTORY_LIMIT = 10


@router.message(F.text == "📜 История генераций")
async def show_generation_history(
    message: Message,
    session: AsyncSession,
) -> None:

    user_repo = UserRepository(session)

    user = await user_repo.get_or_create(
        telegram_id=message.from_user.id,  # type: ignore[union-attr]
        username=(
            message.from_user.username
            if message.from_user
            else None
        ),
    )

    logs = await user_repo.get_recent_generations(
        user,
        limit=HISTORY_LIMIT,
    )

    if not logs:
        await message.answer(
            "📜 <b>История генераций</b>\n\n"
            "У вас пока нет ни одной сгенерированной карточки.\n\n"
            "Нажмите «🆕 Новый товар», чтобы создать первую!"
        )
        return

    titles = [
        log.product_title or "Без названия"
        for log in logs
    ]

    text = (
        "📜 <b>История последних генераций</b>\n\n"
        + "\n\n".join(titles)
    )

    await message.answer(text)
