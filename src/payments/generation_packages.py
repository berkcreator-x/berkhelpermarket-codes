from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class GenerationPackage:
    """
    Пакет генераций.

    frozen=True → защита от случайных изменений
    slots=True → меньше памяти и быстрее доступ (важно для 1000+ пользователей)
    """
    id: str
    title: str
    price_rub: int
    generations: int


GENERATION_PACKAGES: dict[str, GenerationPackage] = {
    "start": GenerationPackage(
        id="start",
        title="Старт",
        price_rub=99,
        generations=10,
    ),
    "business": GenerationPackage(
        id="business",
        title="Бизнес",
        price_rub=399,
        generations=50,
    ),
    "pro": GenerationPackage(
        id="pro",
        title="PRO",
        price_rub=999,
        generations=150,
    ),
}


def get_package(package_id: Any) -> GenerationPackage | None:
    """
    Безопасное получение пакета.

    Fix:
    - защита от str/None/invalid input
    - предотвращает твою ошибку 'str has no attribute price_rub'
    """

    if not isinstance(package_id, str):
        return None

    return GENERATION_PACKAGES.get(package_id)
