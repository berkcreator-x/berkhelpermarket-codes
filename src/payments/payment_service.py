from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from src.models import User
from src.utils import get_logger

logger = get_logger(__name__)


# ==========================================================
# PACKAGES
# ==========================================================

@dataclass(slots=True)
class GenerationPackage:
    price_rub: int
    generations: int


GENERATION_PACKAGES: Dict[str, GenerationPackage] = {
    "basic": GenerationPackage(price_rub=99, generations=20),
    "pro": GenerationPackage(price_rub=199, generations=50),
    "max": GenerationPackage(price_rub=399, generations=120),
}


# ==========================================================
# SERVICE
# ==========================================================

class PaymentService:
    """Логика платежей и выдачи пакетов генераций."""

    def get_package(self, key: str) -> GenerationPackage:
        if key not in GENERATION_PACKAGES:
            raise ValueError(f"Unknown package: {key}")
        return GENERATION_PACKAGES[key]

    async def apply_success_payment(
        self,
        user: User,
        package_key: str,
    ) -> None:
        """Начислить генерации пользователю после оплаты."""

        package = self.get_package(package_key)

        user.generation_balance += package.generations

        logger.info(
            "payment_applied",
            user_id=user.id,
            package=package_key,
            added=package.generations,
        )


# singleton
payment_service = PaymentService()


def get_package(key: str) -> GenerationPackage:
    return payment_service.get_package(key)
