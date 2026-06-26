from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.keyboards import main_menu_keyboard
from src.repositories import UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await state.clear()

    user_repo = UserRepository(session)

    await user_repo.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username if message.from_user else None,
    )

    is_admin = (
        message.from_user is not None
        and message.from_user.id == settings.admin_id
    )

    text = (
        "🚀 Добро пожаловать в BerkHelperMarket\n\n"
        "Ваш ИИ-помощник для создания продающих карточек товаров.\n\n"
        "📈 Что умеет бот:\n"
        "• Генерирует карточки для Wildberries\n"
        "• Создает описания для Ozon\n"
        "• Улучшает существующие карточки\n"
        "• Помогает увеличить продажи\n\n"
        "🎁 Вам доступна бесплатная генерация.\n\n"
        "⚡ В среднем создание карточки занимает 10–30 секунд.\n\n"
        "👇 Выберите нужный раздел:"
    )

    await message.answer(
        text,
        reply_markup=main_menu_keyboard(
            is_admin=is_admin,
        ),
    )


@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cmd_cancel(
    message: Message,
    state: FSMContext,
) -> None:
    current_state = await state.get_state()

    if current_state is None:
        await message.answer(
            "ℹ️ Сейчас нет активного действия."
        )
        return

    await state.clear()

    is_admin = (
        message.from_user is not None
        and message.from_user.id == settings.admin_id
    )

    await message.answer(
        "✅ Действие отменено.",
        reply_markup=main_menu_keyboard(
            is_admin=is_admin,
        ),
    )


@router.message(Command("menu"))
@router.message(F.text == "🏠 Главное меню")
async def cmd_menu(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()

    is_admin = (
        message.from_user is not None
        and message.from_user.id == settings.admin_id
    )

    await message.answer(
        "🏠 Главное меню",
        reply_markup=main_menu_keyboard(
            is_admin=is_admin,
        ),
    )
