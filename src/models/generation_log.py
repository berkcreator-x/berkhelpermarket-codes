from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base
from src.models.enums import GenerationType


if TYPE_CHECKING:
    from src.models.user import User


class GenerationLog(Base):

    __tablename__ = "generation_logs"


    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )


    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )


    type: Mapped[GenerationType] = mapped_column(
        Enum(
            GenerationType,
            name="generation_type",
            values_callable=lambda x: [
                e.value for e in x
            ],
        ),
        nullable=False,
    )


    cost: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )


    quality_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )


    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )


    status: Mapped[str] = mapped_column(
        String(50),
        default="success",
        nullable=False,
    )


    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


    user: Mapped["User"] = relationship(
        back_populates="generation_logs",
    )
