from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.ai.proxyapi_client import ProxyAPIClient, proxyapi_client, ProxyAPIError
from src.ai.prompt_builder import improve_product_prompt, new_product_prompt
from src.exceptions import (
    InsufficientBalanceError,
    AIServiceError,
    GenerationError,
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
# SCHEMA
# ==========================================================

@dataclass(slots=True)
class ProductCard:
    title: str
    description: str
    advantages: list[str] = field(default_factory=list)
    seo: str = ""
    characteristics: list[str] = field(default_factory=list)

    def to_message(self) -> str:
        adv = "\n".join(f"• {a}" for a in self.advantages)
        ch = "\n".join(f"• {c}" for c in self.characteristics)

        parts = [
            f"🏷 <b>Название</b>\n{self.title}",
            f"📝 <b>Описание</b>\n{self.description}",
            f"⭐ <b>Преимущества</b>\n{adv}",
            f"🔍 <b>SEO</b>\n{self.seo}",
        ]

        if self.characteristics:
            parts.append(f"📦 <b>Характеристики</b>\n{ch}")

        return "\n\n".join(parts)


# ==========================================================
# PARSER (MVP, но уже расширяемый)
# ==========================================================

_SECTION_RE = {
    "title": r"🏷.*?Название\s*(.*?)\n(?=📝|$)",
    "description": r"📝.*?Описание\s*(.*?)\n(?=⭐|$)",
    "advantages": r"⭐.*?Преимущества\s*(.*?)\n(?=🔍|$)",
    "seo": r"🔍.*?SEO.*?\s*(.*?)\n(?=📦|$)",
    "characteristics": r"📦.*?Характеристики\s*(.*)",
}


def _parse_list(text: str) -> list[str]:
    return [
        x.strip("•- \t")
        for x in text.splitlines()
        if x.strip()
    ]


def _parse_card(raw: str) -> ProductCard:
    def pick(key: str) -> str:
        m = re.search(_SECTION_RE[key], raw, re.DOTALL)
        return m.group(1).strip() if m else ""

    title = pick("title")
    desc = pick("description")
    adv = _parse_list(pick("advantages"))
    seo = pick("seo")
    ch = _parse_list(pick("characteristics"))

    if not title or not desc:
        raise ProductValidationError("Invalid AI response format")

    return ProductCard(
        title=title,
        description=desc,
        advantages=adv,
        seo=seo,
        characteristics=ch,
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

        prompt = new_product_prompt(name, category, features, audience)
        return await self._run(user, GenerationType.NEW, prompt)

    async def improve_product(
        self,
        user: User,
        existing_text: str,
    ) -> ProductCard:

        prompt = improve_product_prompt(existing_text)
        return await self._run(user, GenerationType.IMPROVE, prompt)

    # ======================================================
    # CORE PIPELINE
    # ======================================================

    async def _run(
        self,
        user: User,
        gen_type: GenerationType,
        prompt: str,
    ) -> ProductCard:

        cost = GENERATION_COSTS[gen_type]

        # 1. BALANCE CHECK
        if user.generation_balance < cost:
            raise InsufficientBalanceError(
                f"Need {cost}, have {user.generation_balance}"
            )

        # 2. AI CALL
        try:
            raw = await self._client.generate(prompt)
        except ProxyAPIError as e:
            logger.error(
                "ai_error",
                user_id=user.id,
                error=str(e),
            )
            raise AIServiceError("AI temporarily unavailable") from e

        # 3. PARSE (before spending balance)
        card = _parse_card(raw)

        # 4. SPEND BALANCE (atomic)
        await self._user_repo.deduct_generations_safe(user, cost)

        # 5. LOG
        await self._user_repo.log_generation(user, gen_type)

        logger.info(
            "generation_success",
            user_id=user.id,
            cost=cost,
            remaining=user.generation_balance,
        )

        return card
