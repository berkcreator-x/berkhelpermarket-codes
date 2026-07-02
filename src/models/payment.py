from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base
from src.models.enums import PaymentStatus

if TYPE_CHECKING:
    from src.models.user import User


class Payment(Base):
    __tablename__ = "payments"

    __table_args__ = (
        Index("ix_payments_label", "label"),
        Index("ix_payments_payment_id", "payment_id"),
        Index("ix_payments_status", "status"),
        Index("ix_payments_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    generations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            name="payment_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=PaymentStatus.PENDING,
        nullable=False,
    )

    payment_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    label: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        back_populates="payments",
    )
