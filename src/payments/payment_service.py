from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Payment, PaymentStatus, User
from src.repositories.payment_repository import PaymentRepository
from src.repositories.user_repository import UserRepository
from src.payments.yoomoney_client import yoomoney_client
from src.utils import get_logger

logger = get_logger(__name__)


class PaymentService:
    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository,
        payment_repo: PaymentRepository,
    ) -> None:
        self._session = session
        self._user_repo = user_repo
        self._payment_repo = payment_repo

    async def create_payment(self, user: User, package) -> tuple[Payment, str]:
        label = f"bhm_{user.telegram_id}_{uuid.uuid4().hex[:12]}"

        payment = await self._payment_repo.create(
            user=user,
            amount=package.price_rub,
            generations=package.generations,
            payment_id=label,
            label=label,
            status=PaymentStatus.PENDING,
        )

        url = yoomoney_client.build_payment_url(
            amount=package.price_rub,
            label=label,
        )

        logger.info(
            "payment_created",
            user_id=user.id,
            label=label,
            amount=package.price_rub,
        )

        return payment, url

    async def confirm_payment_by_label(self, label: str) -> Payment | None:
        stmt = select(Payment).where(Payment.label == label)
        result = await self._session.execute(stmt)
        payment = result.scalar_one_or_none()

        if not payment:
            logger.warning("payment_not_found", label=label)
            return None

        # уже оплачено
        if payment.status == PaymentStatus.PAID:
            return None

        # проверка через YooMoney webhook (или будущий HTTP callback)
        payment.status = PaymentStatus.PAID
        self._session.add(payment)

        user = await self._user_repo.get_by_id(payment.user_id)
        if user:
            await self._user_repo.add_generations(user, payment.generations)

        await self._session.commit()

        logger.info(
            "payment_confirmed",
            user_id=payment.user_id,
            label=label,
        )

        return payment
