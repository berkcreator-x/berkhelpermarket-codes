from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

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
            f"• {item}" for item in self.advantages
        )

        characteristics = "\n".join(
            f"• {item}" for item in self.characteristics
        )

        parts = [
            f"🏷 <b>Название</b>\n{self.title}",
            f"📝 <b>Описание</b>\n{self.description}",
            f"⭐ <b>Преимущества</b>\n{advantages}",
            f"🔍 <b>SEO</b>\n{self.seo}",
        ]

        if self.characteristics:
            parts.append(
                f"📦 <b>Характеристики</b>\n{characteristics}"
            )

        return "\n\n".join(parts)


# ==========================================================
# PARSER
# ==========================================================

_SECTION_RE = {
    "title": r"(?:🏷\s*)?Название\s*(.*?)(?=\n(?:📝|Описание)|\Z)",
    "description": r"(?:📝\s*)?Описание\s*(.*?)(?=\n(?:⭐|Преимущества)|\Z)",
    "advantages": r"(?:⭐\s*)?Преимущества\s*(.*?)(?=\n(?:🔍|SEO)|\Z)",
    "seo": r"(?:🔍\s*)?SEO.*?\s*(.*?)(?=\n(?:📦|Характеристики)|\Z)",
    "characteristics": r"(?:📦\s*)?Характеристики\s*(.*)",
}


def _parse_list(text: str) -> list[str]:
    return [
        item.strip("•-* \t")
        for item in text.splitlines()
        if item.strip()
    ]


def _extract(raw: str, key: str) -> str:
    match = re.search(
        _SECTION_RE[key],
        raw,
        re.DOTALL | re.IGNORECASE,
    )

    if match is None:
        return ""

    return match.group(1).strip()


def _parse_card(raw: str) -> ProductCard:
    title = _extract(raw, "title")
    description = _extract(raw, "description")
    advantages = _parse_list(
        _extract(raw, "advantages")
    )
    seo = _extract(raw, "seo")
    characteristics = _parse_list(
        _extract(raw, "characteristics")
    )

    if not title or not description:

        logger.warning(
            "ai_invalid_structure",
            preview=raw[:400],
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
    # ======================================================
    # CORE PIPELINE
    # ======================================================

    async def _run(
        self,
        user: User,
        gen_type: GenerationType,
        prompt: str,
    ) -> ProductCard:

        started_at = time.perf_counter()

        cost = GENERATION_COSTS[gen_type]

        # --------------------------------------------------
        # 1. Проверка баланса
        # --------------------------------------------------

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

        # --------------------------------------------------
        # 2. Генерация AI
        # --------------------------------------------------

        try:
            raw = await self._client.generate(prompt)

        except ProxyAPIError as exc:

            logger.error(
                "proxyapi_generation_failed",
                user_id=user.id,
                generation_type=gen_type.value,
                prompt_length=len(prompt),
                error=str(exc),
            )

            raise AIServiceError(
                "AI temporarily unavailable."
            ) from exc

        # --------------------------------------------------
        # 3. Проверка пустого ответа
        # --------------------------------------------------

        if not raw or not raw.strip():

            logger.error(
                "proxyapi_empty_response",
                user_id=user.id,
                generation_type=gen_type.value,
            )

            raise AIServiceError(
                "AI returned empty response."
            )

        # --------------------------------------------------
        # 4. Парсинг
        # --------------------------------------------------

        try:
            card = _parse_card(raw)

        except ProductValidationError:

            logger.error(
                "generation_invalid_ai_response",
                user_id=user.id,
                generation_type=gen_type.value,
                preview=raw[:600],
            )

            raise

        # --------------------------------------------------
        # 5. Атомарное списание генераций
        # --------------------------------------------------

        await self._user_repo.deduct_generations_safe(
            user=user,
            amount=cost,
        )

        # --------------------------------------------------
        # 6. Лог генерации
        # --------------------------------------------------

        await self._user_repo.log_generation(
            user=user,
            gen_type=gen_type,
        )

        # --------------------------------------------------
        # 7. Финальный лог
        # --------------------------------------------------

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
