from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.handlers.image_generation import begin_image_generation
from src.handlers.improve_product import begin_improve_product
from src.handlers.new_product import begin_new_product
from src.keyboards import tools_menu_keyboard

router = Router(name="tools_menu")


@router.message(F.text == "🛠 Инструменты")
async def show_tools_menu(message: Message) -> None:

    await message.answer(
        "🛠 <b>Инструменты</b>\n\n"
        "Выбери, что нужно сделать:",
        reply_markup=tools_menu_keyboard(),
    )


@router.callback_query(F.data == "tools:new")
async def tools_new_product(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    if callback.message is None:
        await callback.answer()
        return

    await begin_new_product(
        reply_target=callback.message,  # type: ignore[arg-type]
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        state=state,
        session=session,
    )

    await callback.answer()


@router.callback_query(F.data == "tools:improve")
async def tools_improve_product(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    if callback.message is None:
        await callback.answer()
        return

    await begin_improve_product(
        reply_target=callback.message,  # type: ignore[arg-type]
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        state=state,
        session=session,
    )

    await callback.answer()


@router.callback_query(F.data == "tools:photo")
async def tools_photo_generation(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    if callback.message is None:
        await callback.answer()
        return

    await begin_image_generation(
        reply_target=callback.message,  # type: ignore[arg-type]
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        state=state,
        session=session,
    )

    await callback.answer()
