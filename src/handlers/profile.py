from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import GenerationType
from src.repositories import UserRepository

router = Router(name="profile")


@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message, session: AsyncSession) -> None:
    user_repo = UserRepository(session)
    user = await user_repo.get_or_create(
        telegram_id=message.from_user.id,  # type: ignore[union-attr]
        username=message.from_user.username if message.from_user else None,  # type: ignore[union-attr]
    )

    new_count = await user_repo.count_generations(user, GenerationType.NEW)
    improve_count = await user_repo.count_generations(user, GenerationType.IMPROVE)
    total_count = new_count + improve_count

    text = (
        "👤 <b>Ваш профиль</b>\n\n"
        f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
        f"👤 Username: {('@' + user.username) if user.username else '—'}\n"
        f"📦 Тариф: {user.plan.value}\n"
        f"💎 Баланс генераций: <b>{user.generation_balance}</b>\n\n"
        "📊 <b>Статистика использования</b>\n"
        f"• Новых карточек создано: {new_count}\n"
        f"• Карточек улучшено: {improve_count}\n"
        f"• Всего генераций использовано: {total_count}"
    )

    await message.answer(text)
