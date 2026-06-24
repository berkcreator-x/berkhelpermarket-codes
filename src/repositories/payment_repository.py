from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Payment, PaymentStatus, User


class PaymentRepository:
    """Data access layer for the Payment entity."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user: User,
        amount: float,
        generations: int,
        payment_id: str,
        label: str,
    ) -> Payment:
        payment = Payment(
            user_id=user.id,
            amount=amount,
            generations=generations,
            status=PaymentStatus.PENDING,
            payment_id=payment_id,
            label=label,
        )
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def get_by_label(self, label: str) -> Payment | None:
        stmt = select(Payment).where(Payment.label == label)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_payment_id(self, payment_id: str) -> Payment | None:
        stmt = select(Payment).where(Payment.payment_id == payment_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_paid(self, payment: Payment) -> Payment:
        payment.status = PaymentStatus.PAID
        await self._session.flush()
        return payment

    async def mark_failed(self, payment: Payment) -> Payment:
        payment.status = PaymentStatus.FAILED
        await self._session.flush()
        return payment

    async def list_for_user(self, user: User, limit: int = 20) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
