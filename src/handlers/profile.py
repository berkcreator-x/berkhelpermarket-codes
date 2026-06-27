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

    new_count = await user_repo.count_generations(
        user,
        GenerationType.NEW,
    )

    improve_count = await user_repo.count_generations(
        user,
        GenerationType.IMPROVE,
    )

    total_count = new_count + improve_count

    plan_name = "💎 PRO" if user.plan.value == "pro" else "🎁 FREE"

    username = (
        f"@{user.username}"
        if user.username
        else "Не указан"
    )

    text = (
        "👤 <b>Личный кабинет BerkHelperMarket</b>\n\n"

        f"🪪 Аккаунт: <b>{username}</b>\n"
        f"⚡ Тариф: <b>{plan_name}</b>\n"
        f"💎 Доступно генераций: <b>{user.generation_balance}</b>\n\n"

        "📊 <b>Ваша статистика</b>\n\n"

        f"🆕 Создано карточек: <b>{new_count}</b>\n"
        f"✨ Улучшено карточек: <b>{improve_count}</b>\n"
        f"🚀 Всего использовано генераций: <b>{total_count}</b>\n\n"

        "💡 Используйте генерации для создания "
        "продающих карточек Wildberries и Ozon."
    )

    await message.answer(text)
