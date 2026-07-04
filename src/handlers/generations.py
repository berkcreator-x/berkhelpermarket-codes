from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.keyboards import (
    generation_packages_keyboard,
)
from src.payments import (
    PaymentService,
    get_package,
)
from src.repositories import (
    PaymentRepository,
    UserRepository,
)
from src.utils import get_logger

logger = get_logger(__name__)

router = Router(name="generations")


@router.message(F.text == "💳 Генерации")
async def show_packages(
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

    text = (
        "⚡ <b>Магазин генераций BerkHelperMarket</b>\n\n"

        f"💎 Ваш баланс: <b>{user.generation_balance}</b>\n\n"

        "🔥 <b>Старт</b>\n"
        "10 генераций • 99 ₽\n\n"

        "⭐ <b>Бизнес</b>\n"
        "50 генераций • 399 ₽\n\n"

        "🚀 <b>PRO</b>\n"
        "150 генераций • 999 ₽\n\n"

        "Выберите пакет ниже 👇"
    )

    await message.answer(
        text,
        reply_markup=generation_packages_keyboard(),
    )


@router.callback_query(F.data.startswith("buy_package:"))
async def buy_package(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:

    if (
        callback.data is None
        or callback.message is None
        or callback.from_user is None
    ):
        await callback.answer()
        return

    package_id = callback.data.split(
        ":",
        maxsplit=1,
    )[1]

    package = get_package(package_id)

    if package is None:
        await callback.answer(
            "❌ Пакет не найден.",
            show_alert=True,
        )
        return

    user_repo = UserRepository(session)
    payment_repo = PaymentRepository(session)

    user = await user_repo.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
    )

    payment_service = PaymentService(
        session=session,
        user_repo=user_repo,
        payment_repo=payment_repo,
    )

    _, payment_url = await payment_service.create_payment(
        user=user,
        package=package,
    )

    await callback.message.answer(
        (
            f"💳 <b>{package.title}</b>\n\n"

            f"Стоимость: <b>{package.price_rub:.0f} ₽</b>\n"
            f"Генераций: <b>{package.generations}</b>\n\n"

            "1️⃣ Перейдите по ссылке ниже.\n"
            "2️⃣ Оплатите пакет.\n\n"

            "✅ После успешной оплаты генерации будут начислены автоматически.\n"
            "Бот сам отправит сообщение о зачислении.\n\n"

            f"🔗 {payment_url}"
        )
    )

    await callback.answer()
