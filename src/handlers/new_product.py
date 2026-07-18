from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import (
    AIServiceError,
    GenerationService,
    InsufficientBalanceError,
    ProductValidationError,
)
from src.config import settings
from src.handlers.states import NewProductStates
from src.keyboards import (
    cancel_keyboard,
    main_menu_keyboard,
    platform_select_keyboard,
    skip_price_keyboard,
)
from src.repositories import UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

router = Router(name="new_product")

_PLATFORM_LABELS = {
    "wildberries": "Wildberries",
    "ozon": "Ozon",
    "universal": "Универсальная",
}


async def begin_new_product(
    reply_target: Message,
    telegram_id: int,
    username: str | None,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    user_repo = UserRepository(session)

    user = await user_repo.get_or_create(
        telegram_id=telegram_id,
        username=username,
    )

    if user.generation_balance < 1:
        await reply_target.answer(
            "⚠️ У вас нет генераций для создания карточки.\n\n"
            "Пополните баланс в разделе «💳 Генерации»."
        )
        return

    await state.set_state(
        NewProductStates.waiting_for_name
    )

    await reply_target.answer(
        "🆕 <b>Создание новой карточки товара</b>\n\n"
        "📦 Шаг 1 из 6\n\nКак называется ваш товар?",
        reply_markup=cancel_keyboard(),
    )


@router.message(F.text == "🆕 Новый товар")
async def start_new_product(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    await begin_new_product(
        reply_target=message,
        telegram_id=message.from_user.id,  # type: ignore[union-attr]
        username=(
            message.from_user.username
            if message.from_user
            else None
        ),
        state=state,
        session=session,
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
        "Шаг 2/6. Введите <b>категорию товара</b>\n"
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
        "Шаг 3/6. Опишите <b>особенности товара</b>\n"
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
        "🎯 Шаг 4 из 6\n\n"
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
) -> None:

    if not message.text:
        await message.answer(
            "Пожалуйста, введите текст."
        )
        return

    await state.update_data(
        audience=message.text.strip()
    )

    await state.set_state(
        NewProductStates.waiting_for_platform
    )

    await message.answer(
        "🛍 Шаг 5 из 6\n\n"
        "Для какой площадки готовим карточку?\n\n"
        "<i>От этого зависит длина названия и структура "
        "текста — у Wildberries и Ozon разные требования "
        "к SEO.</i>",
        reply_markup=platform_select_keyboard(),
    )


@router.callback_query(
    NewProductStates.waiting_for_platform,
    F.data.startswith("platform:"),
)
async def process_platform(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:

    if callback.message is None or callback.data is None:
        await callback.answer()
        return

    platform = callback.data.split(":", 1)[1]

    await state.update_data(platform=platform)

    await state.set_state(
        NewProductStates.waiting_for_price
    )

    label = _PLATFORM_LABELS.get(platform, platform)

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Площадка: <b>{label}</b>\n\n"
        "💰 Шаг 6 из 6\n\n"
        "Укажите цену товара (например «1990 руб») — "
        "это поможет подобрать правильный тон текста.\n\n"
        "Если не хотите указывать — нажмите «Пропустить».",
    )

    await callback.message.answer(  # type: ignore[union-attr]
        "Жду цену или нажмите «Пропустить»:",
        reply_markup=skip_price_keyboard(),
    )

    await callback.answer()


@router.callback_query(
    NewProductStates.waiting_for_price,
    F.data == "price:skip",
)
async def process_price_skip(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    if callback.message is None:
        await callback.answer()
        return

    await callback.answer()

    await _finish_new_product(
        message=callback.message,  # type: ignore[arg-type]
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        state=state,
        session=session,
        price=None,
    )


@router.message(
    NewProductStates.waiting_for_price
)
async def process_price_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    if not message.text:
        await message.answer(
            "Пожалуйста, введите текст или нажмите «Пропустить»."
        )
        return

    await _finish_new_product(
        message=message,
        telegram_id=message.from_user.id,  # type: ignore[union-attr]
        username=(
            message.from_user.username
            if message.from_user
            else None
        ),
        state=state,
        session=session,
        price=message.text.strip(),
    )


async def _finish_new_product(
    message: Message,
    telegram_id: int,
    username: str | None,
    state: FSMContext,
    session: AsyncSession,
    price: str | None,
) -> None:

    data = await state.get_data()
    await state.clear()

    user_repo = UserRepository(session)

    user = await user_repo.get_or_create(
        telegram_id=telegram_id,
        username=username,
    )

    is_admin = telegram_id == settings.admin_id

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
            audience=data["audience"],
            platform=data.get("platform", "universal"),
            price=price,
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

    except ProductValidationError:

        logger.warning(
            "new_product_validation_failed",
            user_id=user.id,
        )

        await message.answer(
            "⚠️ Не удалось обработать ответ нейросети.\n\n"
            "Попробуйте ещё раз через несколько секунд.",
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
