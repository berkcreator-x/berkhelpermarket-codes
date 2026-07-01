from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Payment, PaymentStatus, User
from src.payments import GenerationPackage
from src.payments.yoomoney_client import yoomoney_client
from src.repositories.payment_repository import PaymentRepository
from src.repositories.user_repository import UserRepository
from src.utils import get_logger

logger = get_logger(__name__)


class PaymentService:
    """Бизнес-логика платежей BerkHelperMarket."""

    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository,
        payment_repo: PaymentRepository,
    ) -> None:
        self._session = session
        self._user_repo = user_repo
        self._payment_repo = payment_repo

    @staticmethod
    def _generate_label(telegram_id: int) -> str:
        """Создает уникальный label платежа."""
        return f"bhm_{telegram_id}_{uuid.uuid4().hex[:12]}"

    async def create_payment(
        self,
        user: User,
        package: GenerationPackage,
    ) -> tuple[Payment, str]:
        """
        Создать новый платеж.

        Возвращает:
            (Payment, payment_url)
        """

        label = self._generate_label(user.telegram_id)

        payment = await self._payment_repo.create(
            user=user,
            amount=package.price_rub,
            generations=package.generations,
            payment_id=label,
            label=label,
        )

        payment_url = yoomoney_client.build_payment_url(
            amount=package.price_rub,
            label=label,
        )

        logger.info(
            "payment_created",
            payment_id=payment.id,
            user_id=user.id,
            label=label,
            amount=package.price_rub,
            generations=package.generations,
        )

        return payment, payment_url

    async def confirm_payment_by_label(
        self,
        label: str,
    ) -> Payment | None:
        """
        Подтвердить платеж.

        Метод полностью идемпотентный.

        Повторный вызов никогда не начислит генерации повторно.
        """

        payment = await self._payment_repo.get_by_label(
            label,
            for_update=True,
        )

        if payment is None:
            logger.warning(
                "payment_not_found",
                label=label,
            )
            return None

        if payment.status == PaymentStatus.PAID:
            logger.info(
                "payment_already_confirmed",
                label=label,
            )
            return payment

        user = await self._user_repo.get_by_id(payment.user_id)

        if user is None:
            logger.error(
                "payment_user_not_found",
                payment_id=payment.id,
                user_id=payment.user_id,
            )
            return None

        await self._payment_repo.mark_paid(payment)

        await self._user_repo.add_generations(
            user,
            payment.generations,
        )

        await self._session.commit()

        logger.info(
            "payment_confirmed",
            payment_id=payment.id,
            user_id=user.id,
            generations=payment.generations,
            new_balance=user.generation_balance,
        )

        return payment
