from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.ai.proxyapi_client import ProxyAPIClient, ProxyAPIError, proxyapi_client
from src.ai.prompt_builder import improve_product_prompt, new_product_prompt
from src.models import GenerationType, User
from src.repositories import UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

GENERATION_COSTS: dict[GenerationType, int] = {
    GenerationType.NEW: 1,
    GenerationType.IMPROVE: 2,
}


class InsufficientBalanceError(Exception):
    """Пользователь не имеет достаточного баланса генераций."""


class GenerationServiceError(Exception):
    """Ошибка при выполнении AI-генерации."""


@dataclass(slots=True)
class ProductCard:
    title: str
    description: str
    advantages: list[str]
    seo: str
    characteristics: list[str] = field(default_factory=list)

    def to_message(self) -> str:
        advantages_block = "\n".join(f"• {item}" for item in self.advantages)
        characteristics_block = "\n".join(f"• {item}" for item in self.characteristics)

        parts = [
            f"🏷 <b>Название</b>\n{self.title}",
            f"📝 <b>Описание</b>\n{self.description}",
            f"⭐ <b>Преимущества</b>\n{advantages_block}",
            f"🔍 <b>SEO-ключи</b>\n{self.seo}",
        ]
        if self.characteristics:
            parts.append(f"📦 <b>Характеристики</b>\n{characteristics_block}")

        return "\n\n".join(parts)


# Порядок секций для парсера (с emoji-маркерами нового формата)
_SECTIONS = [
    ("🏷 Название", "title"),
    ("📝 Описание", "description"),
    ("⭐ Преимущества", "advantages"),
    ("🔍 SEO-ключи", "seo"),
    ("📦 Характеристики", "characteristics"),
]

# Fallback-секции без emoji (на случай если модель опустит их)
_SECTION_ALIASES: dict[str, str] = {
    "название": "🏷 Название",
    "описание": "📝 Описание",
    "преимущества": "⭐ Преимущества",
    "seo": "🔍 SEO-ключи",
    "seo-ключи": "🔍 SEO-ключи",
    "seo ключи": "🔍 SEO-ключи",
    "характеристики": "📦 Характеристики",
}


def _normalize_text(raw: str) -> str:
    """Нормализуем текст: заменяем alias-секции на каноничные."""
    for alias, canonical in _SECTION_ALIASES.items():
        # Заменяем строки вида "Название\n" → "🏷 Название\n"
        raw = re.sub(
            rf"(?im)^{re.escape(alias)}\s*$",
            canonical,
            raw,
        )
    return raw


def _extract_section(text: str, header: str, next_headers: list[str]) -> str:
    """Извлечь содержимое секции между header и следующим заголовком."""
    next_pattern = "|".join(re.escape(h) for h in next_headers)
    if next_pattern:
        pattern = rf"{re.escape(header)}\s*\n(.*?)(?=\n(?:{next_pattern})|\Z)"
    else:
        pattern = rf"{re.escape(header)}\s*\n(.*?)(?:\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _parse_list_block(raw: str) -> list[str]:
    """Преобразовать блок с дефисами/точками в список строк."""
    return [
        line.strip("-•·*– \t")
        for line in raw.splitlines()
        if line.strip("-•·*– \t")
    ]


def _parse_card(raw_text: str) -> ProductCard:
    """Распарсить структурированный ответ модели в ProductCard."""
    text = _normalize_text(raw_text)

    section_headers = [s[0] for s in _SECTIONS]
    extracted: dict[str, str] = {}

    for i, (header, key) in enumerate(_SECTIONS):
        next_headers = section_headers[i + 1:]
        extracted[key] = _extract_section(text, header, next_headers)

    title = extracted.get("title", "")
    description = extracted.get("description", "")
    advantages_raw = extracted.get("advantages", "")
    seo = extracted.get("seo", "")
    characteristics_raw = extracted.get("characteristics", "")

    advantages = _parse_list_block(advantages_raw)
    characteristics = _parse_list_block(characteristics_raw)

    if not title or not description:
        logger.warning(
            "ai_unparseable_response",
            raw_preview=raw_text[:500],
            extracted_title=title,
            extracted_description=description[:100] if description else "",
        )
        raise GenerationServiceError(
            "Сервис временно недоступен. Попробуйте позже."
        )

    return ProductCard(
        title=title,
        description=description,
        advantages=advantages,
        seo=seo or "—",
        characteristics=characteristics,
    )


class GenerationService:
    """Оркестрирует проверку баланса, AI-запрос и логирование генераций."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo
        self._client: ProxyAPIClient = proxyapi_client

    async def generate_new_product(
        self, user: User, name: str, category: str, features: str, audience: str
    ) -> ProductCard:
        return await self._run(
            user=user,
            gen_type=GenerationType.NEW,
            prompt=new_product_prompt(name, category, features, audience),
        )

    async def improve_product(self, user: User, existing_text: str) -> ProductCard:
        return await self._run(
            user=user,
            gen_type=GenerationType.IMPROVE,
            prompt=improve_product_prompt(existing_text),
        )

    async def _run(self, user: User, gen_type: GenerationType, prompt: str) -> ProductCard:
        cost = GENERATION_COSTS[gen_type]

        # ШАГ 1: Проверка баланса ДО вызова AI (быстрая, без блокировки)
        if user.generation_balance < cost:
            raise InsufficientBalanceError(
                f"Недостаточно генераций: нужно {cost}, "
                f"доступно {user.generation_balance}"
            )

        # ШАГ 2: Вызов AI (баланс ещё не списан)
        try:
            raw_text = await self._client.generate(prompt)
        except ProxyAPIError as exc:
            logger.error(
                "ai_generation_failed",
                user_id=user.id,
                gen_type=gen_type.value,
                status_code=exc.status_code,
                error=str(exc),
            )
            # Баланс НЕ списывается при ошибке AI
            raise GenerationServiceError(
                "Сервис временно недоступен. Попробуйте позже."
            ) from exc

        # ШАГ 3: Парсинг ответа (до списания — если ответ нечитаемый, баланс не трогаем)
        card = _parse_card(raw_text)

        # ШАГ 4: Атомарное списание через SELECT FOR UPDATE (защита от race conditions)
        await self._user_repo.deduct_generations_safe(user, cost)
        await self._user_repo.log_generation(user, gen_type)

        logger.info(
            "generation_success",
            user_id=user.id,
            gen_type=gen_type.value,
            cost=cost,
            remaining_balance=user.generation_balance,
        )

        return card
