from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.handlers.states import AdminGrantStates
from src.keyboards import admin_panel_keyboard, admin_users_pagination_keyboard, main_menu_keyboard
from src.models import GenerationLog, GenerationType, Payment, PaymentStatus
from src.repositories import UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

router = Router(name="admin")


def _is_admin(telegram_id: int | None) -> bool:
    return telegram_id is not None and telegram_id == settings.admin_id


@router.message(F.text == "⚙️ Панель")
async def open_admin_panel(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return

    await message.answer("⚙️ <b>Админ-панель</b>", reply_markup=admin_panel_keyboard())


@router.callback_query(F.data == "admin:menu")
async def admin_menu(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id) or callback.message is None:
        await callback.answer()
        return

    await callback.message.edit_text("⚙️ <b>Админ-панель</b>", reply_markup=admin_panel_keyboard())  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id) or callback.message is None:
        await callback.answer()
        return

    user_repo = UserRepository(session)
    total_users = await user_repo.count_all()

    total_generations = (await session.execute(select(func.count()).select_from(GenerationLog))).scalar_one()
    new_generations = (
        await session.execute(
            select(func.count()).select_from(GenerationLog).where(GenerationLog.type == GenerationType.NEW)
        )
    ).scalar_one()
    improve_generations = (
        await session.execute(
            select(func.count())
            .select_from(GenerationLog)
            .where(GenerationLog.type == GenerationType.IMPROVE)
        )
    ).scalar_one()
    total_paid_amount = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == PaymentStatus.PAID)
        )
    ).scalar_one()
    total_payments_paid = (
        await session.execute(
            select(func.count()).select_from(Payment).where(Payment.status == PaymentStatus.PAID)
        )
    ).scalar_one()

    text = (
        "📊 <b>Статистика системы</b>\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"🧠 Всего генераций: {total_generations}\n"
        f"   • Новых карточек: {new_generations}\n"
        f"   • Улучшений: {improve_generations}\n\n"
        f"💳 Успешных платежей: {total_payments_paid}\n"
        f"💰 Общая сумма: {float(total_paid_amount):.2f}₽"
    )

    await callback.message.edit_text(text, reply_markup=admin_panel_keyboard())  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data.startswith("admin:users:"))
async def admin_users(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id) or callback.message is None or callback.data is None:
        await callback.answer()
        return

    offset = int(callback.data.split(":")[2])
    user_repo = UserRepository(session)
    users = await user_repo.list_all(limit=10, offset=offset)
    total = await user_repo.count_all()
    has_more = offset + 10 < total

    if not users:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "👥 Пользователи не найдены.", reply_markup=admin_panel_keyboard()
        )
        await callback.answer()
        return

    lines = [f"👥 <b>Пользователи</b> ({offset + 1}–{offset + len(users)} из {total})\n"]
    for u in users:
        username = f"@{u.username}" if u.username else "—"
        lines.append(f"ID {u.id} | TG {u.telegram_id} | {username} | баланс: {u.generation_balance}")

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines), reply_markup=admin_users_pagination_keyboard(offset, has_more)
    )
    await callback.answer()


@router.callback_query(F.data == "admin:grant")
async def admin_grant_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id) or callback.message is None:
        await callback.answer()
        return

    await state.set_state(AdminGrantStates.waiting_for_telegram_id)
    await callback.message.answer(  # type: ignore[union-attr]
        "Введите Telegram ID пользователя, которому нужно выдать генерации:"
    )
    await callback.answer()


@router.message(AdminGrantStates.waiting_for_telegram_id)
async def admin_grant_telegram_id(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return

    if not message.text or not message.text.strip().lstrip("-").isdigit():
        await message.answer("Введите корректный числовой Telegram ID.")
        return

    await state.update_data(telegram_id=int(message.text.strip()))
    await state.set_state(AdminGrantStates.waiting_for_amount)
    await message.answer("Введите количество генераций для начисления (целое число, отрицательное — для списания):")


@router.message(AdminGrantStates.waiting_for_amount)
async def admin_grant_amount(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return

    if not message.text or not message.text.strip().lstrip("-").isdigit():
        await message.answer("Введите корректное целое число.")
        return

    amount = int(message.text.strip())
    data = await state.get_data()
    telegram_id = data["telegram_id"]
    await state.clear()

    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(telegram_id)
    if user is None:
        await message.answer(
            "Пользователь с таким Telegram ID ещё не запускал бота.",
            reply_markup=main_menu_keyboard(is_admin=True),
        )
        return

    new_balance = max(user.generation_balance + amount, 0)
    await user_repo.set_balance(user, new_balance)

    logger.info("admin_balance_adjusted", target_telegram_id=telegram_id, amount=amount, new_balance=new_balance)

    await message.answer(
        f"✅ Баланс пользователя {telegram_id} изменён на {amount:+d}. Новый баланс: {new_balance}.",
        reply_markup=main_menu_keyboard(is_admin=True),
    )
