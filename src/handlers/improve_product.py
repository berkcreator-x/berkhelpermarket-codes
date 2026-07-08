from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import (
    AIServiceError,
    GenerationService,
    InsufficientBalanceError,
    ProductValidationError,
)
from src.config import settings
from src.handlers.states import ImproveProductStates
from src.keyboards import cancel_keyboard, main_menu_keyboard
from src.repositories import UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

router = Router(name="improve_product")


@router.message(F.text == "✨ Улучшить товар")
async def start_improve_product(
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

    if user.generation_balance < 2:
        await message.answer(
            "⚠️ Для улучшения карточки нужно <b>2 генерации</b>, "
            f"а у вас сейчас <b>{user.generation_balance}</b>.\n\n"
            "Пополните баланс в разделе «💳 Генерации»."
        )
        return

    await state.set_state(
        ImproveProductStates.waiting_for_text
    )

    await message.answer(
        "✨ <b>Улучшение карточки товара</b>\n\n"
        "Вставьте текущее описание товара "
        "(можно скопировать прямо с маркетплейса):",
        reply_markup=cancel_keyboard(),
    )


@router.message(
    ImproveProductStates.waiting_for_text
)
async def process_improve_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    if not message.text:
        await message.answer(
            "Пожалуйста, отправьте текстовое описание товара."
        )
        return

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
        "⏳ Улучшаю карточку товара, это займёт 10–30 секунд…"
    )

    generation_service = GenerationService(user_repo)

    try:
        card = await generation_service.improve_product(
            user=user,
            existing_text=message.text.strip(),
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
            "improve_product_validation_failed",
            user_id=user.id,
        )

        await message.answer(
            "⚠️ Не удалось обработать ответ нейросети.\n\n"
            "Попробуйте ещё раз.",
            reply_markup=main_menu_keyboard(
                is_admin=is_admin,
            ),
        )

        return

    except AIServiceError:
        await message.answer(
            "❌ Сервис временно недоступен. Попробуйте позже.",
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
        f"✅ Списано 2 генерации. "
        f"Остаток: <b>{user.generation_balance}</b>."
    )
