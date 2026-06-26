from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base
from src.models.enums import PlanType

if TYPE_CHECKING:
    from src.models.generation_log import GenerationLog
    from src.models.payment import Payment


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
        nullable=False,
    )

    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    plan: Mapped[PlanType] = mapped_column(
        Enum(
            PlanType,
            name="plan_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=PlanType.FREE,
        nullable=False,
    )

    generation_balance: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    generation_logs: Mapped[list["GenerationLog"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    payments: Mapped[list["Payment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<User id={self.id} "
            f"telegram_id={self.telegram_id} "
            f"balance={self.generation_balance}>"
        )
