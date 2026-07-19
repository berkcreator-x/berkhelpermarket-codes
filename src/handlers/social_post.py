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
from src.handlers.states import SocialPostStates
from src.keyboards import (
    cancel_keyboard,
    main_menu_keyboard,
    social_platform_keyboard,
)
from src.repositories import UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

router = Router(name="social_post")

SOCIAL_POST_COST = 2

_PLATFORM_LABELS = {
    "telegram": "Telegram",
    "vk": "VK",
}


async def begin_social_post(
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

    if user.generation_balance < SOCIAL_POST_COST:
        await reply_target.answer(
            f"⚠️ Для поста нужно "
            f"<b>{SOCIAL_POST_COST} генерации</b>, "
            f"а у вас сейчас <b>{user.generation_balance}</b>.\n\n"
            "Пополните баланс в разделе «💳 Генерации»."
        )
        return

    await state.set_state(
        SocialPostStates.waiting_for_idea
    )

    await reply_target.answer(
        "📢 <b>Пост для соцсетей</b>\n\n"
        "Опишите товар или идею для поста — "
        "коротко, своими словами:",
        reply_markup=cancel_keyboard(),
    )


@router.message(
    SocialPostStates.waiting_for_idea
)
async def process_social_idea(
    message: Message,
    state: FSMContext,
) -> None:

    if not message.text:
        await message.answer(
            "Пожалуйста, отправьте текстовое описание."
        )
        return

    await state.update_data(
        idea=message.text.strip()
    )

    await state.set_state(
        SocialPostStates.waiting_for_platform
    )

    await message.answer(
        "📱 Для какой площадки пишем пост?",
        reply_markup=social_platform_keyboard(),
    )


@router.callback_query(
    SocialPostStates.waiting_for_platform,
    F.data.startswith("social:"),
)
async def process_social_platform(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    if callback.message is None or callback.data is None:
        await callback.answer()
        return

    platform = callback.data.split(":", 1)[1]

    data = await state.get_data()
    await state.clear()

    await callback.answer()

    label = _PLATFORM_LABELS.get(platform, platform)

    user_repo = UserRepository(session)

    user = await user_repo.get_or_create(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
    )

    is_admin = (
        callback.from_user.id == settings.admin_id
    )

    await callback.message.answer(  # type: ignore[union-attr]
        f"⏳ Пишу пост под {label}, это займёт "
        "10–20 секунд…"
    )

    generation_service = GenerationService(user_repo)

    try:
        post = await generation_service.generate_social_post(
            user=user,
            idea=data.get("idea", ""),
            platform=platform,
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
            "social_post_validation_failed",
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
        post.to_message(),
        reply_markup=main_menu_keyboard(
            is_admin=is_admin,
        ),
    )

    await callback.message.answer(  # type: ignore[union-attr]
        f"✅ Списано {SOCIAL_POST_COST} генерации. "
        f"Остаток: <b>{user.generation_balance}</b>."
    )
