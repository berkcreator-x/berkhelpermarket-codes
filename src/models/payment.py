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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base
from src.models.enums import PaymentStatus

if TYPE_CHECKING:
    from src.models.user import User

STRING_LENGTH = 255


class Payment(Base):
    __tablename__ = "payments"

    __table_args__ = (
        Index("ix_payments_label", "label"),
        Index("ix_payments_payment_id", "payment_id"),
        Index("ix_payments_status", "status"),
        Index("ix_payments_user_id", "user_id"),
        Index("ix_payments_order_number", "order_number"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Человекочитаемый номер заказа для отображения
    # пользователю ("Заказ №1042"). Заполняется БД
    # через последовательность payment_order_seq.
    order_number: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
        server_default=text("nextval('payment_order_seq')"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
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
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=PaymentStatus.PENDING,
        nullable=False,
    )

    payment_id: Mapped[str] = mapped_column(
        String(STRING_LENGTH),
        unique=True,
        nullable=False,
    )

    label: Mapped[str] = mapped_column(
        String(STRING_LENGTH),
        unique=True,
        nullable=False,
    )

    # Источник/провайдер оплаты. Сейчас всегда "yoomoney",
    # но поле готово под добавление новых платёжных систем
    # (СБП, карта напрямую, крипта и т.д.) без миграции схемы.
    source: Mapped[str] = mapped_column(
        String(50),
        default="yoomoney",
        server_default="yoomoney",
        nullable=False,
    )

    # Номер операции в системе платёжного провайдера
    # (у YooMoney это operation_id из вебхука). Не совпадает
    # с нашим внутренним label/payment_id — нужен для сверки
    # с личным кабинетом провайдера при спорных ситуациях.
    provider_transaction_id: Mapped[str | None] = mapped_column(
        String(STRING_LENGTH),
        nullable=True,
    )

    # Момент фактического подтверждения оплаты
    # (в отличие от created_at — момента создания ссылки).
    paid_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Payment("
            f"id={self.id}, "
            f"order_number={self.order_number}, "
            f"user_id={self.user_id}, "
            f"status={self.status.value}, "
            f"amount={self.amount}, "
            f"generations={self.generations}"
            f")>"
        )

    def __str__(self) -> str:
        return (
            f"Payment("
            f"id={self.id}, "
            f"order_number={self.order_number}, "
            f"status={self.status.value}, "
            f"label={self.label}"
            f")"
        )
