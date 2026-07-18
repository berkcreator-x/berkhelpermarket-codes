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
from src.handlers.states import ProductAnalysisStates
from src.keyboards import cancel_keyboard, main_menu_keyboard
from src.repositories import UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

router = Router(name="product_analysis")

ANALYSIS_COST = 1


async def begin_product_analysis(
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

    if user.generation_balance < ANALYSIS_COST:
        await reply_target.answer(
            f"⚠️ Для анализа карточки нужна "
            f"<b>{ANALYSIS_COST} генерация</b>, "
            f"а у вас сейчас <b>{user.generation_balance}</b>.\n\n"
            "Пополните баланс в разделе «💳 Генерации»."
        )
        return

    await state.set_state(
        ProductAnalysisStates.waiting_for_text
    )

    await reply_target.answer(
        "📊 <b>Анализ карточки товара</b>\n\n"
        "Вставьте текст карточки — свой или конкурента "
        "(можно скопировать прямо с маркетплейса). "
        "Получите оценку, сильные и слабые стороны, "
        "недостающие SEO-ключи и рекомендации.",
        reply_markup=cancel_keyboard(),
    )


@router.message(
    ProductAnalysisStates.waiting_for_text
)
async def process_analysis_text(
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
        "⏳ Анализирую карточку, это займёт 10–20 секунд…"
    )

    generation_service = GenerationService(user_repo)

    try:
        analysis = await generation_service.analyze_product(
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
            "product_analysis_validation_failed",
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
        analysis.to_message(),
        reply_markup=main_menu_keyboard(
            is_admin=is_admin,
        ),
    )

    await message.answer(
        f"✅ Списана {ANALYSIS_COST} генерация. "
        f"Остаток: <b>{user.generation_balance}</b>."
    )
