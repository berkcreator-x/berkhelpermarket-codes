from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, InputMediaPhoto, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.generation_service import GENERATION_COSTS, GenerationService
from src.exceptions import (
    AIServiceError,
    ImageGenerationError,
    InsufficientBalanceError,
    ProductValidationError,
)
from src.handlers.states import ImageGenerationStates
from src.keyboards import cancel_keyboard
from src.models import GenerationType
from src.repositories import UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

router = Router(name="image_generation")

IMAGES_COST = GENERATION_COSTS[GenerationType.IMAGES]


async def begin_image_generation(
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
            "⚠️ У вас нет генераций для создания изображений.\n\n"
            "Пополните баланс в разделе «💳 Генерации»."
        )
        return

    await state.set_state(
        ImageGenerationStates.waiting_for_photo
    )

    await reply_target.answer(
        "🖼 <b>Улучшение фото товара</b>\n\n"
        f"Полный комплект из 5 изображений стоит "
        f"{IMAGES_COST} генераций "
        f"(сейчас у вас {user.generation_balance}).\n\n"
        "Пришлите фото своего товара — ИИ сохранит сам товар "
        "и сделает вокруг него профессиональное оформление.",
        reply_markup=cancel_keyboard(),
    )


@router.message(
    ImageGenerationStates.waiting_for_photo,
    F.photo,
)
async def process_photo(
    message: Message,
    state: FSMContext,
) -> None:

    photo = message.photo[-1]  # type: ignore[index]

    await state.update_data(photo_file_id=photo.file_id)
    await state.set_state(
        ImageGenerationStates.waiting_for_style
    )

    await message.answer(
        "🎨 Опишите желаемый стиль оформления.\n\n"
        "Например: «минимализм», «премиум чёрный фон», "
        "«яркий летний стиль». Можно просто написать "
        "«на свой вкус»."
    )


@router.message(ImageGenerationStates.waiting_for_photo)
async def process_photo_invalid(message: Message) -> None:
    await message.answer(
        "Пришлите, пожалуйста, именно фото товара "
        "(не файл и не текст)."
    )


@router.message(ImageGenerationStates.waiting_for_style)
async def process_style(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:

    if not message.text:
        await message.answer(
            "Опишите стиль текстом (или напишите «на свой вкус»)."
        )
        return

    data = await state.get_data()
    file_id = data.get("photo_file_id")

    await state.clear()

    if not file_id:
        await message.answer(
            "Что-то пошло не так, начните заново через "
            "«🛠 Инструменты»."
        )
        return

    user_repo = UserRepository(session)

    user = await user_repo.get_or_create(
        telegram_id=message.from_user.id,  # type: ignore[union-attr]
        username=(
            message.from_user.username
            if message.from_user
            else None
        ),
    )

    status_message = await message.answer(
        "⏳ Генерирую изображения, это может занять "
        "до пары минут..."
    )

    try:
        photo_io = await message.bot.download(file_id)  # type: ignore[union-attr]
        photo_bytes = photo_io.read()
    except Exception:
        logger.exception(
            "photo_download_failed",
            user_id=user.id,
        )
        await status_message.edit_text(
            "⚠️ Не получилось скачать фото. Попробуйте ещё раз "
            "через «🛠 Инструменты»."
        )
        return

    service = GenerationService(user_repo=user_repo)

    try:
        images, failed_count = await service.generate_product_images(
            user=user,
            photo_bytes=photo_bytes,
            style_wishes=message.text,
        )
    except InsufficientBalanceError:
        await status_message.edit_text(
            "⚠️ Недостаточно генераций для этой операции."
        )
        return
    except (
        AIServiceError,
        ImageGenerationError,
        ProductValidationError,
    ):
        await status_message.edit_text(
            "⚠️ Не получилось сгенерировать изображения. "
            "Попробуйте позже."
        )
        return
    except Exception:
        logger.exception(
            "image_generation_unexpected_error",
            user_id=user.id,
        )
        await status_message.edit_text(
            "⚠️ Произошла непредвиденная ошибка. "
            "Попробуйте позже."
        )
        return

    media = [
        InputMediaPhoto(
            media=BufferedInputFile(
                image,
                filename=f"product_image_{index}.png",
            )
        )
        for index, image in enumerate(images, start=1)
    ]

    await message.answer_media_group(media)

    note = ""
    if failed_count:
        note = (
            f"\n\n⚠️ {failed_count} из 5 не удалось "
            "сгенерировать — генерации за них не списаны."
        )

    await status_message.edit_text(
        f"✅ Готово! Списано {len(images)} генераций.\n"
        f"Баланс: {user.generation_balance}{note}"
    )
