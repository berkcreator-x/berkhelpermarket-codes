from __future__ import annotations

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
    improve_product_prompt,
    new_product_prompt,
)
from src.exceptions import (
    AIServiceError,
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
}


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

    return str(value).strip()


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

    return [str(value)]


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

    return ProductCard(
        title=title,
        description=description,
        advantages=advantages,
        seo=seo,
        characteristics=characteristics,
    )


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

        card = await self._generate_card(
            user,
            gen_type,
            prompt,
        )

        await self._user_repo.deduct_generations_safe(
            user=user,
            amount=cost,
        )
        await self._user_repo.log_generation(
            user=user,
            gen_type=gen_type,
        )
        duration_ms = int(
            (time.perf_counter() - started_at) * 1000
        )
        logger.info(
            "generation_completed",
            user_id=user.id,
            generation_type=gen_type.value,
            spent=cost,
            balance=user.generation_balance,
            duration_ms=duration_ms,
            prompt_length=len(prompt),
        )
        return card

    async def _generate_card(
        self,
        user: User,
        gen_type: GenerationType,
        prompt: str,
    ) -> ProductCard:
        last_raw = ""
        for attempt in (1, 2):
            raw = await self._call_ai(
                user,
                gen_type,
                prompt,
                attempt,
            )
            last_raw = raw
            try:
                return _parse_card(raw)
            except ProductValidationError:
                if attempt == 2:
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
    ) -> str:
        request_prompt = prompt
        if attempt == 2:
            request_prompt = (
                f"{prompt}\n\n"
                "ВАЖНО.\n"
                "Предыдущий ответ оказался невалидным.\n"
                "Верни ТОЛЬКО корректный JSON.\n"
                "Без markdown.\n"
                "Без ```.\n"
                "Без текста до JSON.\n"
                "Без текста после JSON."
            )
        try:
            raw = await self._client.generate(
                request_prompt
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
        if not raw.strip():
            logger.error(
                "proxyapi_empty_response",
                user_id=user.id,
                generation_type=gen_type.value,
            )
            raise AIServiceError(
                "AI returned empty response."
            )
        return raw
