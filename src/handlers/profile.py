from __future__ import annotations

import datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.keyboards import profile_nav_keyboard
from src.models import GenerationType, Payment, PaymentStatus, User
from src.payments import GENERATION_PACKAGES
from src.repositories import GenerationStats, PaymentRepository, UserRepository

router = Router(name="profile")

HISTORY_LIMIT = 10
PURCHASES_LIMIT = 10

_RU_MONTHS = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр",
    5: "май", 6: "июн", 7: "июл", 8: "авг",
    9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}

_RU_MONTHS_FULL = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

_STATUS_ICON = {
    PaymentStatus.PAID: "✅",
    PaymentStatus.PENDING: "⏳",
    PaymentStatus.FAILED: "❌",
    PaymentStatus.CANCELED: "❌",
}

_STATUS_SUFFIX = {
    PaymentStatus.PAID: "",
    PaymentStatus.PENDING: " (ожидает оплаты)",
    PaymentStatus.FAILED: " (не прошёл)",
    PaymentStatus.CANCELED: " (отменён)",
}


def _format_date(dt: datetime.datetime) -> str:
    return f"{dt.day} {_RU_MONTHS[dt.month]}"


def _format_full_date(dt: datetime.datetime) -> str:
    return f"{dt.day} {_RU_MONTHS_FULL[dt.month]} {dt.year}"


def _package_title(payment: Payment) -> str:

    for package in GENERATION_PACKAGES.values():
        if package.generations == payment.generations:
            return package.title

    return f"{payment.generations} ген."


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


async def _build_purchases_text(
    payment_repo: PaymentRepository,
    user: User,
) -> str:

    payments = await payment_repo.list_for_user(
        user,
        limit=PURCHASES_LIMIT,
    )

    if not payments:
        return (
            "🛒 <b>История покупок</b>\n\n"
            "У вас пока нет ни одной покупки.\n\n"
            "Загляните в «💳 Генерации», чтобы выбрать пакет."
        )

    paid_payments = [
        p for p in payments if p.status == PaymentStatus.PAID
    ]

    total_spent = sum(
        (p.amount for p in paid_payments),
        Decimal("0"),
    )

    total_generations = sum(
        p.generations for p in paid_payments
    )

    lines = [
        f"💰 Всего потрачено: <b>{total_spent:.0f}₽</b>",
        f"📦 Куплено генераций: <b>{total_generations}</b>",
        "",
        "━━━━━━━━━━━━━━",
        "",
    ]

    for payment in payments:
        icon = _STATUS_ICON[payment.status]
        suffix = _STATUS_SUFFIX[payment.status]
        title = _package_title(payment)
        date = _format_date(payment.created_at)

        lines.append(
            f"{icon} {date} — {title} "
            f"({payment.generations} ген.) — "
            f"{payment.amount:.0f}₽{suffix}"
        )

    return (
        "🛒 <b>История покупок</b>\n\n"
        + "\n".join(lines)
    )


async def _build_stats_text(
    user_repo: UserRepository,
    user: User,
) -> str:

    stats: GenerationStats = await user_repo.get_generation_stats(
        user
    )

    if stats.avg_quality is not None:
        quality_line = f"{stats.avg_quality:.0f}/100"
    else:
        quality_line = "нет данных"

    if stats.avg_duration_ms is not None:
        duration_line = f"{stats.avg_duration_ms / 1000:.1f} сек."
    else:
        duration_line = "нет данных"

    if stats.last_generation_at is not None:
        last_generation_line = _format_full_date(
            stats.last_generation_at
        )
    else:
        last_generation_line = "ещё не было"

    registered_line = _format_full_date(user.created_at)

    return (
        "📊 <b>Моя статистика</b>\n\n"

        f"🚀 Всего генераций: <b>{stats.total}</b>\n"
        f"🆕 Новых товаров: <b>{stats.new_count}</b>\n"
        f"✨ Улучшений: <b>{stats.improve_count}</b>\n"
        f"💎 Потрачено генераций: <b>{stats.total_cost}</b>\n\n"

        f"⭐ Средняя оценка качества AI: <b>{quality_line}</b>\n"
        f"⏱ Среднее время генерации: <b>{duration_line}</b>\n\n"

        f"📅 Дата регистрации: <b>{registered_line}</b>\n"
        f"🕐 Последняя генерация: <b>{last_generation_line}</b>"
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
    payment_repo = PaymentRepository(session)

    user = await user_repo.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
    )

    if view == "history":
        text = await _build_history_text(user_repo, user)
    elif view == "purchases":
        text = await _build_purchases_text(payment_repo, user)
    elif view == "stats":
        text = await _build_stats_text(user_repo, user)
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
