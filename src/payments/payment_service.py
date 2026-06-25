from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select

from src.models import Payment, PaymentStatus, User
from src.payments.yoomoney_client import yoomoney_client
from src.repositories import PaymentRepository, UserRepository
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GenerationPackage:
    """Пакет генераций для покупки."""

    id: str
    title: str
    generations: int
    price_rub: float


GENERATION_PACKAGES: list[GenerationPackage] = [
    GenerationPackage(id="pack_10",  title="10 генераций",  generations=10,  price_rub=139.0),
    GenerationPackage(id="pack_50",  title="50 генераций",  generations=50,  price_rub=599.0),
    GenerationPackage(id="pack_150", title="150 генераций", generations=150, price_rub=1499.0),
]


def get_package(package_id: str) -> GenerationPackage | None:
    return next((p for p in GENERATION_PACKAGES if p.id == package_id), None)


class PaymentService:
    """Управляет созданием и подтверждением платежей ЮMoney.

    AI-логика никогда не вызывается из этого сервиса.
    Платежи и генерации строго разделены.
    """

    def __init__(self, user_repo: UserRepository, payment_repo: PaymentRepository) -> None:
        self._user_repo = user_repo
        self._payment_repo = payment_repo

    async def create_payment(
        self, user: User, package: GenerationPackage
    ) -> tuple[Payment, str]:
        """Создать платёж в статусе pending и вернуть (payment, url)."""
        label = f"bhm_{user.telegram_id}_{uuid.uuid4().hex[:12]}"
        # YooMoney quickpay не возвращает operation_id заранее — label = payment_id
        payment_id = label

        payment = await self._payment_repo.create(
            user=user,
            amount=package.price_rub,
            generations=package.generations,
            payment_id=payment_id,
            label=label,
        )
        payment_url = yoomoney_client.build_payment_url(
            amount=package.price_rub, label=label
        )

        logger.info(
            "payment_created",
            user_id=user.id,
            label=label,
            amount=package.price_rub,
            generations=package.generations,
        )
        return payment, payment_url

    async def confirm_payment_by_label(self, label: str) -> Payment | None:
        """Проверить и подтвердить платёж по label.

        Идемпотентен: повторные вызовы с тем же label не начисляют генерации дважды.
        Использует SELECT FOR UPDATE для защиты от конкурентных webhook-запросов.
        Возвращает Payment если платёж был только что подтверждён, иначе None.
        """
        session = self._payment_repo._session

        # SELECT FOR UPDATE — блокируем строку платежа на время транзакции
        stmt = (
            select(Payment)
            .where(Payment.label == label)
            .with_for_update()
        )
        result = await session.execute(stmt)
        payment = result.scalar_one_or_none()

        if payment is None:
            logger.warning("payment_not_found", label=label)
            return None

        # Идемпотентность: уже оплачен — ничего не делаем
        if payment.status == PaymentStatus.PAID:
            logger.info("payment_already_confirmed", label=label)
            return None

        # Проверка через API ЮMoney
        is_paid = await yoomoney_client.verify_payment(label)
        if not is_paid:
            logger.info("payment_not_confirmed_yet", label=label)
            return None

        # Атомарно обновляем статус и начисляем генерации
        payment = await self._payment_repo.mark_paid(payment)
        user = await self._user_repo.get_by_id(payment.user_id)
        if user is not None:
            await self._user_repo.add_generations(user, payment.generations)
            logger.info(
                "payment_confirmed",
                user_id=user.id,
                label=label,
                generations_added=payment.generations,
                new_balance=user.generation_balance,
            )
        else:
            logger.error("payment_user_not_found", label=label, user_id=payment.user_id)

        return payment
