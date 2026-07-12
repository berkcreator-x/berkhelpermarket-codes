from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.keyboards import profile_nav_keyboard
from src.models import GenerationType, User
from src.repositories import UserRepository

router = Router(name="profile")

HISTORY_LIMIT = 10


async def _build_profile_text(
    user_repo: UserRepository,
    user: User,
) -> str:

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

    return (
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


async def _build_history_text(
    user_repo: UserRepository,
    user: User,
) -> str:

    logs = await user_repo.get_recent_generations(
        user,
        limit=HISTORY_LIMIT,
    )

    if not logs:
        return (
            "📜 <b>История генераций</b>\n\n"
            "У вас пока нет ни одной сгенерированной карточки.\n\n"
            "Нажмите «🆕 Новый товар», чтобы создать первую!"
        )

    titles = [
        log.product_title or "Без названия"
        for log in logs
    ]

    return (
        "📜 <b>История последних генераций</b>\n\n"
        + "\n\n".join(titles)
    )


def _build_purchases_text() -> str:

    return (
        "🛒 <b>История покупок</b>\n\n"
        "Эта функция скоро появится!\n\n"
        "Здесь будет отображаться история пополнений "
        "баланса генераций и оплаченных тарифов."
    )


@router.message(F.text == "👤 Профиль")
async def show_profile(
    message: Message,
    session: AsyncSession,
) -> None:

    user_repo = UserRepository(session)

    user = await user_repo.get_or_create(
        telegram_id=message.from_user.id,  # type: ignore[union-attr]
        username=message.from_user.username if message.from_user else None,  # type: ignore[union-attr]
    )

    text = await _build_profile_text(user_repo, user)

    await message.answer(
        text,
        reply_markup=profile_nav_keyboard(),
    )


@router.callback_query(F.data.startswith("profile_nav:"))
async def profile_navigate(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:

    if callback.message is None or callback.data is None:
        await callback.answer()
        return

    view = callback.data.split(":", 1)[1]

    user_repo = UserRepository(session)

    user = await user_repo.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
    )

    if view == "history":
        text = await _build_history_text(user_repo, user)
    elif view == "purchases":
        text = _build_purchases_text()
    else:
        text = await _build_profile_text(user_repo, user)

    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            text,
            reply_markup=profile_nav_keyboard(),
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise

    await callback.answer()
