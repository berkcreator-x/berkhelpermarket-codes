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
from src.handlers.states import ImproveProductStates
from src.keyboards import (
    cancel_keyboard,
    improve_focus_keyboard,
    main_menu_keyboard,
    platform_select_keyboard,
)
from src.repositories import UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

router = Router(name="improve_product")

_PLATFORM_LABELS = {
    "wildberries": "Wildberries",
    "ozon": "Ozon",
    "universal": "Универсальная",
}

_FOCUS_LABELS = {
    "all": "Полная переработка",
    "seo": "Только SEO и ключи",
    "description": "Только описание",
    "advantages": "Только преимущества",
}


async def begin_improve_product(
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
            "⚠️ Для улучшения карточки нужна минимум "
            f"<b>1 генерация</b>, а у вас сейчас "
            f"<b>{user.generation_balance}</b>.\n\n"
            "Пополните баланс в разделе «💳 Генерации»."
        )
        return

    await state.set_state(
        ImproveProductStates.waiting_for_text
    )

    await reply_target.answer(
        "✨ <b>Улучшение карточки товара</b>\n\n"
        "Вставьте текущее описание товара "
        "(можно скопировать прямо с маркетплейса):",
        reply_markup=cancel_keyboard(),
    )


@router.message(F.text == "✨ Улучшить товар")
async def start_improve_product(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    await begin_improve_product(
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
    ImproveProductStates.waiting_for_text
)
async def process_improve_text(
    message: Message,
    state: FSMContext,
) -> None:

    if not message.text:
        await message.answer(
            "Пожалуйста, отправьте текстовое описание товара."
        )
        return

    await state.update_data(
        existing_text=message.text.strip()
    )

    await state.set_state(
        ImproveProductStates.waiting_for_platform
    )

    await message.answer(
        "🛍 Для какой площадки улучшаем карточку?",
        reply_markup=platform_select_keyboard(),
    )


@router.callback_query(
    ImproveProductStates.waiting_for_platform,
    F.data.startswith("platform:"),
)
async def process_improve_platform(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:

    if callback.message is None or callback.data is None:
        await callback.answer()
        return

    platform = callback.data.split(":", 1)[1]

    await state.update_data(platform=platform)
    await state.set_state(
        ImproveProductStates.waiting_for_focus
    )

    label = _PLATFORM_LABELS.get(platform, platform)

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Площадка: <b>{label}</b>\n\n"
        "Что именно улучшить?",
    )

    await callback.message.answer(  # type: ignore[union-attr]
        "Выберите вариант:",
        reply_markup=improve_focus_keyboard(),
    )

    await callback.answer()


@router.callback_query(
    ImproveProductStates.waiting_for_focus,
    F.data.startswith("focus:"),
)
async def process_improve_focus(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    if callback.message is None or callback.data is None:
        await callback.answer()
        return

    focus = callback.data.split(":", 1)[1]

    data = await state.get_data()
    await state.clear()

    await callback.answer()

    user_repo = UserRepository(session)

    user = await user_repo.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
    )

    cost = 2 if focus == "all" else 1

    if user.generation_balance < cost:
        await callback.message.answer(  # type: ignore[union-attr]
            f"⚠️ Для этого варианта нужно "
            f"<b>{cost} генераций</b>, а у вас сейчас "
            f"<b>{user.generation_balance}</b>.\n\n"
            "Пополните баланс в разделе «💳 Генерации»."
        )
        return

    is_admin = (
        callback.from_user.id == settings.admin_id
    )

    label = _FOCUS_LABELS.get(focus, focus)

    await callback.message.answer(  # type: ignore[union-attr]
        f"⏳ Улучшаю карточку ({label.lower()}), "
        "это займёт 10–30 секунд…"
    )

    generation_service = GenerationService(user_repo)

    try:
        card = await generation_service.improve_product(
            user=user,
            existing_text=data.get("existing_text", ""),
            platform=data.get("platform", "universal"),
            focus=focus,
        )

    except InsufficientBalanceError:
        await callback.message.answer(  # type: ignore[union-attr]
            "⚠️ Недостаточно генераций. "
            "Пополните баланс в разделе «💳 Генерации».",
            reply_markup=main_menu_keyboard(
                is_admin=is_admin,
            ),
        )
        return

    except ProductValidationError:

        logger.warning(
            "improve_product_validation_failed",
            user_id=user.id,
        )

        await callback.message.answer(  # type: ignore[union-attr]
            "⚠️ Не удалось обработать ответ нейросети.\n\n"
            "Попробуйте ещё раз.",
            reply_markup=main_menu_keyboard(
                is_admin=is_admin,
            ),
        )

        return

    except AIServiceError:
        await callback.message.answer(  # type: ignore[union-attr]
            "❌ Сервис временно недоступен. Попробуйте позже.",
            reply_markup=main_menu_keyboard(
                is_admin=is_admin,
            ),
        )
        return

    await callback.message.answer(  # type: ignore[union-attr]
        card.to_message(),
        reply_markup=main_menu_keyboard(
            is_admin=is_admin,
        ),
    )

    await callback.message.answer(  # type: ignore[union-attr]
        f"✅ Списано {cost} "
        f"{'генерация' if cost == 1 else 'генерации'}. "
        f"Остаток: <b>{user.generation_balance}</b>."
    )
