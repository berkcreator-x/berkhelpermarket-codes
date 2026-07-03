from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import (
    AIServiceError,
    GenerationService,
    InsufficientBalanceError,
)
from src.config import settings
from src.handlers.states import NewProductStates
from src.keyboards import cancel_keyboard, main_menu_keyboard
from src.repositories import UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

router = Router(name="new_product")


@router.message(F.text == "🆕 Новый товар")
async def start_new_product(
    message: Message,
    state: FSMContext,
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

    if user.generation_balance < 1:
        await message.answer(
            "⚠️ У вас нет генераций для создания карточки.\n\n"
            "Пополните баланс в разделе «💳 Генерации»."
        )
        return

    await state.set_state(
        NewProductStates.waiting_for_name
    )

    await message.answer(
        "🆕 <b>Создание новой карточки товара</b>\n\n"
        "📦 Шаг 1 из 4\n\nКак называется ваш товар?",
        reply_markup=cancel_keyboard(),
    )


@router.message(
    NewProductStates.waiting_for_name
)
async def process_name(
    message: Message,
    state: FSMContext,
) -> None:

    if not message.text:
        await message.answer(
            "Пожалуйста, введите текст."
        )
        return

    await state.update_data(
        name=message.text.strip()
    )

    await state.set_state(
        NewProductStates.waiting_for_category
    )

    await message.answer(
        "Шаг 2/4. Введите <b>категорию товара</b>\n"
        "<i>Например: Кухня, Электроника, Одежда, Спорт</i>"
    )


@router.message(
    NewProductStates.waiting_for_category
)
async def process_category(
    message: Message,
    state: FSMContext,
) -> None:

    if not message.text:
        await message.answer(
            "Пожалуйста, введите текст."
        )
        return

    await state.update_data(
        category=message.text.strip()
    )

    await state.set_state(
        NewProductStates.waiting_for_features
    )

    await message.answer(
        "Шаг 3/4. Опишите <b>особенности товара</b>\n"
        "<i>Материал, размер, функции, уникальные свойства</i>"
    )


@router.message(
    NewProductStates.waiting_for_features
)
async def process_features(
    message: Message,
    state: FSMContext,
) -> None:

    if not message.text:
        await message.answer(
            "Пожалуйста, введите текст."
        )
        return

    await state.update_data(
        features=message.text.strip()
    )

    await state.set_state(
        NewProductStates.waiting_for_audience
    )

    await message.answer(
        "🎯 Шаг 4 из 4\n\n"
        "Для кого предназначен товар?\n\n"
        "Например:\n"
        "• женщины 25–45 лет\n"
        "• автомобилисты\n"
        "• владельцы кошек\n\n"
        "<i>Кому подойдёт этот товар?</i>"
    )


@router.message(
    NewProductStates.waiting_for_audience
)
async def process_audience(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    if not message.text:
        await message.answer(
            "Пожалуйста, введите текст."
        )
        return

    data = await state.get_data()
    await state.clear()

    user_repo = UserRepository(session)

    user = await user_repo.get_or_create(
        telegram_id=message.from_user.id,  # type: ignore[union-attr]
        username=(
            message.from_user.username
            if message.from_user
            else None
        ),
    )

    is_admin = (
        message.from_user is not None
        and message.from_user.id == settings.admin_id
    )

    await message.answer(
        "🧠 Анализирую товар...\n"
        "📊 Изучаю целевую аудиторию...\n"
        "✍️ Формирую продающий текст...\n\n"
        "Это займет 10–30 секунд."
    )

    generation_service = GenerationService(user_repo)

    try:
        card = await generation_service.generate_new_product(
            user=user,
            name=data["name"],
            category=data["category"],
            features=data["features"],
            audience=message.text.strip(),
        )

    except InsufficientBalanceError:
        await message.answer(
            "⚠️ Недостаточно генераций. "
            "Пополните баланс в разделе «💳 Генерации».",
            reply_markup=main_menu_keyboard(
                is_admin=is_admin,
            ),
        )
        return

    except AIServiceError:
        await message.answer(
            "⚠️ Генерация временно недоступна.\n\n"
            "Наш ИИ сейчас перегружен.\n"
            "Попробуйте позже.",
            reply_markup=main_menu_keyboard(
                is_admin=is_admin,
            ),
        )
        return

    await message.answer(
        card.to_message(),
        reply_markup=main_menu_keyboard(
            is_admin=is_admin,
        ),
    )

    await message.answer(
        f"✅ Списана 1 генерация. "
        f"Остаток: <b>{user.generation_balance}</b>."
    )
