from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.enums import PaymentStatus
from src.models.payment import Payment
from src.models.user import User


class PaymentRepository:
    """
    Репозиторий платежей.

    Отвечает только за работу с БД.
    Не содержит бизнес-логики.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # =====================================================
    # CREATE
    # =====================================================

    async def create(
        self,
        *,
        user: User,
        amount: Decimal,
        generations: int,
        payment_id: str,
        label: str,
    ) -> Payment:
        payment = Payment(
            user_id=user.id,
            amount=amount,
            generations=generations,
            payment_id=payment_id,
            label=label,
            status=PaymentStatus.PENDING,
        )

        self._session.add(payment)
        await self._session.flush()

        return payment

    # =====================================================
    # GETTERS
    # =====================================================

    async def get_by_id(
        self,
        payment_id: int,
    ) -> Payment | None:
        return await self._session.get(Payment, payment_id)

    async def get_by_label(
        self,
        label: str,
        *,
        for_update: bool = False,
    ) -> Payment | None:
        stmt = (
            select(Payment)
            .where(Payment.label == label)
        )

        if for_update:
            stmt = stmt.with_for_update()

        result = await self._session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_payment_id(
        self,
        payment_id: str,
    ) -> Payment | None:
        stmt = (
            select(Payment)
            .where(Payment.payment_id == payment_id)
        )

        result = await self._session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_with_user(
        self,
        label: str,
        *,
        for_update: bool = False,
    ) -> Payment | None:
        """
        Получить платеж сразу вместе с пользователем.
        Полезно для webhook и админки.
        """

        stmt = (
            select(Payment)
            .options(selectinload(Payment.user))
            .where(Payment.label == label)
        )

        if for_update:
            stmt = stmt.with_for_update()

        result = await self._session.execute(stmt)

        return result.scalar_one_or_none()

    # =====================================================
    # STATUS
    # =====================================================

    async def mark_paid(
        self,
        payment: Payment,
    ) -> Payment:
        payment.status = PaymentStatus.PAID
        await self._session.flush()
        return payment

    async def mark_failed(
        self,
        payment: Payment,
    ) -> Payment:
        payment.status = PaymentStatus.FAILED
        await self._session.flush()
        return payment

    async def mark_canceled(
        self,
        payment: Payment,
    ) -> Payment:
        payment.status = PaymentStatus.CANCELED
        await self._session.flush()
        return payment

    # =====================================================
    # LISTS
    # =====================================================

    async def list_for_user(
        self,
        user: User,
        limit: int = 20,
    ) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)

        return list(result.scalars().all())

    async def list_pending(
        self,
        limit: int = 100,
    ) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.status == PaymentStatus.PENDING)
            .order_by(Payment.created_at.asc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)

        return list(result.scalars().all())
