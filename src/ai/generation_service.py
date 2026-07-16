from __future__ import annotations

import asyncio
import html
import json
import time
from dataclasses import dataclass, field
from typing import Any

from src.ai.proxyapi_client import (
    ProxyAPIClient,
    ProxyAPIError,
    proxyapi_client,
)
from src.ai.prompt_builder import (
    image_prompts_prompt,
    improve_product_prompt,
    new_product_prompt,
)
from src.exceptions import (
    AIServiceError,
    ImageGenerationError,
    InsufficientBalanceError,
    ProductValidationError,
)
from src.models import GenerationType, User
from src.repositories import UserRepository
from src.utils import get_logger

logger = get_logger(__name__)


# ==========================================================
# COSTS
# ==========================================================

GENERATION_COSTS: dict[GenerationType, int] = {
    GenerationType.NEW: 1,
    GenerationType.IMPROVE: 2,
    GenerationType.IMAGES: 5,
}

IMAGES_PER_BATCH = 5
MIN_SUCCESSFUL_IMAGES = 1


# ==========================================================
# AI VALIDATION
# ==========================================================

MAX_AI_ATTEMPTS = 2

MIN_TITLE_LENGTH = 20
MAX_TITLE_LENGTH = 80
MIN_DESCRIPTION_LENGTH = 200

MIN_ADVANTAGES = 5
MIN_CHARACTERISTICS = 3
MIN_SEO_KEYWORDS = 10

QUALITY_SCORE_TO_ACCEPT = 70


# ==========================================================
# PRODUCT CARD
# ==========================================================

@dataclass(slots=True, frozen=True)
class ProductCard:
    title: str
    description: str
    advantages: list[str] = field(default_factory=list)
    seo: str = ""
    characteristics: list[str] = field(default_factory=list)

    def to_message(self) -> str:

        advantages = "\n".join(
            f"• {html.escape(item)}"
            for item in self.advantages
        )

        characteristics = "\n".join(
            f"• {html.escape(item)}"
            for item in self.characteristics
        )

        parts = [
            f"🏷 <b>Название</b>\n{html.escape(self.title)}",
            f"📝 <b>Описание</b>\n{html.escape(self.description)}",
            f"⭐ <b>Преимущества</b>\n{advantages}",
            f"🔍 <b>SEO</b>\n{html.escape(self.seo)}",
        ]

        if self.characteristics:
            parts.append(
                f"📦 <b>Характеристики</b>\n{characteristics}"
            )

        return "\n\n".join(parts)


# ==========================================================
# JSON PARSER
# ==========================================================

def _strip_code_fence(raw: str) -> str:

    text = raw.strip()

    if text.startswith("```"):

        parts = text.split("```")

        if len(parts) >= 2:
            text = parts[1].strip()

            if text.lower().startswith("json"):
                text = text[4:].strip()

    return text


def _extract_json(raw: str) -> str:

    text = _strip_code_fence(raw)

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        return text

    return text[start : end + 1]


def _normalize_string(value: Any) -> str:

    if value is None:
        return ""

    if isinstance(value, list):
        return "\n".join(
            str(x).strip()
            for x in value
            if str(x).strip()
        )

    return (
        str(value)
        .replace("\r", "")
        .strip()
    )


def _normalize_list(value: Any) -> list[str]:

    if value is None:
        return []

    if isinstance(value, list):

        return [
            str(x).strip(" -*•\t")
            for x in value
            if str(x).strip()
        ]

    if isinstance(value, str):

        if "," in value and "\n" not in value:

            return [
                item.strip(" -*•")
                for item in value.split(",")
                if item.strip()
            ]

        return [
            item.strip(" -*•")
            for item in value.splitlines()
            if item.strip()
        ]

    return [
        str(value).strip(" -*•\t")
    ]


def _count_seo_keywords(seo: str) -> int:

    if not seo:
        return 0

    return len(
        [
            item.strip()
            for item in seo.replace("\n", ",").split(",")
            if item.strip()
        ]
    )


def _calculate_quality_score(
    card: ProductCard,
) -> int:

    score = 0

    # TITLE

    if len(card.title) >= MIN_TITLE_LENGTH:
        score += 20

    # DESCRIPTION

    if len(card.description) >= MIN_DESCRIPTION_LENGTH:
        score += 30

    # ADVANTAGES

    if len(card.advantages) >= MIN_ADVANTAGES:
        score += 20

    # SEO

    if (
        _count_seo_keywords(card.seo)
        >= MIN_SEO_KEYWORDS
    ):
        score += 20

    # CHARACTERISTICS

    if (
        len(card.characteristics)
        >= MIN_CHARACTERISTICS
    ):
        score += 10

    return score


def _validate_card(
    card: ProductCard,
) -> None:

    if len(card.title) < MIN_TITLE_LENGTH:

        raise ProductValidationError(
            "Title too short."
        )

    if len(card.title) > MAX_TITLE_LENGTH:

        raise ProductValidationError(
            "Title too long."
        )

    if len(card.description) < MIN_DESCRIPTION_LENGTH:

        raise ProductValidationError(
            "Description too short."
        )

    if len(card.advantages) < MIN_ADVANTAGES:

        raise ProductValidationError(
            "Too few advantages."
        )

    if (
        _count_seo_keywords(card.seo)
        < MIN_SEO_KEYWORDS
    ):

        raise ProductValidationError(
            "Too few SEO keywords."
        )

    if (
        len(card.characteristics)
        < MIN_CHARACTERISTICS
    ):

        raise ProductValidationError(
            "Too few characteristics."
        )


def _parse_card(raw: str) -> ProductCard:

    candidate = _extract_json(raw)

    try:

        payload = json.loads(candidate)

    except Exception as exc:

        logger.warning(
            "ai_json_decode_failed",
            preview=raw[:400],
            error=str(exc),
        )

        raise ProductValidationError(
            "AI returned invalid JSON."
        ) from exc

    if not isinstance(payload, dict):

        raise ProductValidationError(
            "JSON root must be object."
        )

    payload = {
        str(k).lower().strip(): v
        for k, v in payload.items()
    }

    payload = {
        k: v
        for k, v in payload.items()
        if v is not None
    }

    title = _normalize_string(
        payload.get("title")
    )

    description = _normalize_string(
        payload.get("description")
    )

    advantages = _normalize_list(
        payload.get("advantages")
    )

    seo = _normalize_string(
        payload.get("seo")
    )

    characteristics = _normalize_list(
        payload.get("characteristics")
    )

    if not title or not description:

        logger.warning(
            "ai_invalid_structure",
            preview=raw[:300],
        )

        raise ProductValidationError(
            "AI returned invalid response."
        )

    card = ProductCard(
        title=title,
        description=description,
        advantages=advantages,
        seo=seo,
        characteristics=characteristics,
    )

    return card


# ==========================================================
# SERVICE
# ==========================================================

class GenerationService:

    def __init__(
        self,
        user_repo: UserRepository,
        client: ProxyAPIClient = proxyapi_client,
    ) -> None:

        self._user_repo = user_repo
        self._client = client

    async def generate_new_product(
        self,
        user: User,
        name: str,
        category: str,
        features: str,
        audience: str,
    ) -> ProductCard:

        prompt = new_product_prompt(
            name,
            category,
            features,
            audience,
        )

        return await self._run(
            user,
            GenerationType.NEW,
            prompt,
        )

    async def improve_product(
        self,
        user: User,
        existing_text: str,
    ) -> ProductCard:

        prompt = improve_product_prompt(
            existing_text,
        )

        return await self._run(
            user,
            GenerationType.IMPROVE,
            prompt,
        )

    async def generate_product_images(
        self,
        user: User,
        photo_bytes: bytes,
        style_wishes: str,
    ) -> tuple[list[bytes], int]:
        """
        Генерирует до 5 продающих изображений на основе
        реального фото товара пользователя.

        Списывает генерации ТОЛЬКО за реально успешно
        сгенерированные изображения (частичный успех —
        не повод забирать полную стоимость).

        Возвращает (список готовых изображений, сколько
        из 5 не удалось сгенерировать).
        """

        started_at = time.perf_counter()

        if user.generation_balance < 1:
            raise InsufficientBalanceError(
                f"Need at least 1, have "
                f"{user.generation_balance}"
            )

        prompts = await self._build_image_prompts(
            user, style_wishes
        )

        results = await asyncio.gather(
            *(
                self._client.edit_image(
                    image_bytes=photo_bytes,
                    prompt=prompt,
                )
                for prompt in prompts
            ),
            return_exceptions=True,
        )

        images: list[bytes] = []

        for result in results:

            if isinstance(result, (bytes, bytearray)):
                images.append(bytes(result))
            else:
                logger.warning(
                    "image_generation_item_failed",
                    user_id=user.id,
                    error=str(result),
                )

        failed_count = len(prompts) - len(images)

        if len(images) < MIN_SUCCESSFUL_IMAGES:

            logger.error(
                "image_generation_all_failed",
                user_id=user.id,
            )

            raise ImageGenerationError(
                "Не удалось сгенерировать ни одного "
                "изображения. Попробуйте позже."
            )

        cost = len(images)

        if user.generation_balance < cost:
            cost = user.generation_balance

        await self._user_repo.deduct_generations_safe(
            user=user,
            amount=cost,
        )

        duration_ms = int(
            (time.perf_counter() - started_at) * 1000
        )

        status = "success" if failed_count == 0 else "partial"

        await self._user_repo.log_generation(
            user=user,
            gen_type=GenerationType.IMAGES,
            cost=cost,
            duration_ms=duration_ms,
            status=status,
        )

        logger.info(
            "images_generated",
            user_id=user.id,
            requested=len(prompts),
            succeeded=len(images),
            failed=failed_count,
            cost=cost,
            balance=user.generation_balance,
            duration_ms=duration_ms,
        )

        return images, failed_count

    async def _build_image_prompts(
        self,
        user: User,
        style_wishes: str,
    ) -> list[str]:

        prompt = image_prompts_prompt(style_wishes)

        raw = await self._call_ai(
            user=user,
            gen_type=GenerationType.IMAGES,
            prompt=prompt,
            attempt=1,
        )

        try:

            candidate = _extract_json(raw)
            payload = json.loads(candidate)
            prompts = payload.get("prompts")

            if (
                not isinstance(prompts, list)
                or len(prompts) == 0
            ):
                raise ValueError(
                    "prompts missing or empty"
                )

            cleaned = [
                str(item).strip()
                for item in prompts
                if str(item).strip()
            ]

            if not cleaned:
                raise ValueError("prompts empty after clean")

            return cleaned[:IMAGES_PER_BATCH]

        except Exception as exc:

            logger.error(
                "image_prompts_parse_failed",
                preview=raw[:300],
                error=str(exc),
            )

            raise ProductValidationError(
                "AI вернул некорректный список промптов "
                "для изображений."
            ) from exc

    async def _run(
        self,
        user: User,
        gen_type: GenerationType,
        prompt: str,
    ) -> ProductCard:

        started_at = time.perf_counter()

        cost = GENERATION_COSTS[gen_type]

        if user.generation_balance < cost:

            logger.info(
                "generation_not_enough_balance",
                user_id=user.id,
                required=cost,
                current=user.generation_balance,
            )

            raise InsufficientBalanceError(
                f"Need {cost}, have {user.generation_balance}"
            )

        card, quality = await self._generate_card(
            user,
            gen_type,
            prompt,
        )

        await self._user_repo.deduct_generations_safe(
            user=user,
            amount=cost,
        )

        duration_ms = int(
            (time.perf_counter() - started_at) * 1000
        )

        await self._user_repo.log_generation(
            user=user,
            gen_type=gen_type,
            product_title=card.title,
            cost=cost,
            quality_score=quality,
            duration_ms=duration_ms,
        )

        logger.info(
            "generation_completed",
            user_id=user.id,
            generation_type=gen_type.value,
            spent=cost,
            balance=user.generation_balance,
            duration_ms=duration_ms,
            prompt_length=len(prompt),
            quality=quality,
        )
        return card

    async def _generate_card(
        self,
        user: User,
        gen_type: GenerationType,
        prompt: str,
    ) -> tuple[ProductCard, int]:

        last_raw = ""
        last_reason = ""

        for attempt in range(
            1,
            MAX_AI_ATTEMPTS + 1,
        ):

            raw = await self._call_ai(
                user,
                gen_type,
                prompt,
                attempt,
                last_reason,
            )

            last_raw = raw

            try:

                card = _parse_card(raw)

                _validate_card(card)

                quality = _calculate_quality_score(
                    card
                )

                logger.info(
                    "generation_quality",
                    user_id=user.id,
                    generation_type=gen_type.value,
                    quality=quality,
                )

                if (
                    quality
                    < QUALITY_SCORE_TO_ACCEPT
                ):

                    logger.warning(
                        "generation_quality_retry",
                        user_id=user.id,
                        quality=quality,
                    )

                    if attempt < MAX_AI_ATTEMPTS:
                        last_reason = (
                            "Low quality score "
                            f"({quality}/{QUALITY_SCORE_TO_ACCEPT})."
                        )
                        continue

                return card, quality

            except ProductValidationError as exc:

                last_reason = str(exc)

                logger.warning(
                    "generation_validation_failed",
                    user_id=user.id,
                    generation_type=gen_type.value,
                    reason=str(exc),
                )

                if attempt == MAX_AI_ATTEMPTS:

                    logger.error(
                        "generation_invalid_ai_response",
                        user_id=user.id,
                        generation_type=gen_type.value,
                        preview=last_raw[:600],
                    )

                    raise

                logger.warning(
                    "generation_retry_invalid_json",
                    user_id=user.id,
                    generation_type=gen_type.value,
                )

        raise ProductValidationError(
            "AI returned invalid response."
        )

    async def _call_ai(
        self,
        user: User,
        gen_type: GenerationType,
        prompt: str,
        attempt: int,
        reason: str = "",
    ) -> str:
        request_prompt = prompt
        if attempt > 1:

            reason_text = (
                reason
                or "недостаточное качество либо неверный JSON"
            )

            request_prompt = (
                f"{prompt}\n\n"
                "ПРЕДЫДУЩИЙ ОТВЕТ БЫЛ ОТКЛОНЕН.\n\n"
                f"Причина: {reason_text}\n\n"
                "Исправь ответ.\n\n"
                "Строго соблюдай формат.\n\n"
                "Ответ должен:\n"
                "- начинаться с {\n"
                "- заканчиваться }\n"
                "- не содержать markdown\n"
                "- не содержать комментариев\n"
                "- не содержать пояснений\n"
                "- не содержать ```\n"
                "- не содержать текста вне JSON\n"
            )
        try:
            raw = await self._client.generate(
                request_prompt
            )
            raw = raw.strip()
            logger.info(
                "ai_response_length",
                user_id=user.id,
                generation_type=gen_type.value,
                length=len(raw),
            )
            logger.debug(
                "ai_preview",
                preview=raw[:200],
            )
        except ProxyAPIError as exc:
            logger.error(
                "proxyapi_generation_failed",
                user_id=user.id,
                generation_type=gen_type.value,
                prompt_length=len(request_prompt),
                error=str(exc),
            )
            raise AIServiceError(
                "AI temporarily unavailable."
            ) from exc
        if not raw:
            logger.error(
                "proxyapi_empty_response",
                user_id=user.id,
                generation_type=gen_type.value,
            )
            raise AIServiceError(
                "AI returned empty response."
            )
        return raw
