from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.keyboards import generation_packages_keyboard, payment_check_keyboard
from src.payments import GENERATION_PACKAGES, PaymentService, get_package
from src.repositories import PaymentRepository, UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

router = Router(name="generations")


@router.message(F.text == "💎 Генерации")
async def show_packages(message: Message, session: AsyncSession) -> None:
    user_repo = UserRepository(session)
    user = await user_repo.get_or_create(
        telegram_id=message.from_user.id,  # type: ignore[union-attr]
        username=message.from_user.username if message.from_user else None,  # type: ignore[union-attr]
    )

    lines = ["💳 <b>Покупка генераций</b>\n", f"Текущий баланс: <b>{user.generation_balance}</b>\n"]
    for pkg in GENERATION_PACKAGES:
        lines.append(f"• {pkg.title} — {pkg.price_rub:.0f}₽")

    await message.answer("\n".join(lines), reply_markup=generation_packages_keyboard())


@router.callback_query(F.data.startswith("buy_package:"))
async def buy_package(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None or callback.message is None or callback.from_user is None:
        await callback.answer()
        return

    package_id = callback.data.split(":", maxsplit=1)[1]
    package = get_package(package_id)
    if package is None:
        await callback.answer("Пакет не найден.", show_alert=True)
        return

    user_repo = UserRepository(session)
    payment_repo = PaymentRepository(session)
    user = await user_repo.get_or_create(
        telegram_id=callback.from_user.id, username=callback.from_user.username
    )

    payment_service = PaymentService(user_repo, payment_repo)
    payment, payment_url = await payment_service.create_payment(user=user, package=package)

    await callback.message.answer(  # type: ignore[union-attr]
        f"💳 Оплата пакета «{package.title}» — {package.price_rub:.0f}₽\n\n"
        f"1️⃣ Перейдите по ссылке и оплатите:\n{payment_url}\n\n"
        "2️⃣ После оплаты нажмите кнопку «Я оплатил» ниже — генерации будут начислены автоматически.",
        reply_markup=payment_check_keyboard(payment.label),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("check_payment:"))
async def check_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return

    label = callback.data.split(":", maxsplit=1)[1]

    user_repo = UserRepository(session)
    payment_repo = PaymentRepository(session)
    payment_service = PaymentService(user_repo, payment_repo)

    payment = await payment_repo.get_by_label(label)
    if payment is None:
        await callback.answer("Платёж не найден.", show_alert=True)
        return

    if payment.status.value == "paid":
        await callback.answer("✅ Этот платёж уже подтверждён.", show_alert=True)
        return

    confirmed = await payment_service.confirm_payment_by_label(label)
    if confirmed is not None:
        user = await user_repo.get_by_id(confirmed.user_id)
        balance = user.generation_balance if user else "—"
        await callback.message.answer(  # type: ignore[union-attr]
            f"✅ Оплата подтверждена! Начислено {confirmed.generations} генераций.\n"
            f"Текущий баланс: <b>{balance}</b>."
        )
        await callback.answer("Оплата подтверждена ✅")
    else:
        await callback.answer(
            "⏳ Платёж пока не найден. Если вы только оплатили, подождите немного и попробуйте снова.",
            show_alert=True,
        )
