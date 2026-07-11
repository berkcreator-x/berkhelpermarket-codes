from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
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
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    type: Mapped[GenerationType] = mapped_column(
        Enum(
            GenerationType,
            name="generation_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )

    # ==========================================================
    # GENERATED PRODUCT
    # ==========================================================

    title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    advantages: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    seo: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    characteristics: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    quality_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    ai_model: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        back_populates="generation_logs",
    )

    def __repr__(self) -> str:
        return (
            f"<GenerationLog "
            f"id={self.id} "
            f"user_id={self.user_id} "
            f"type={self.type.value} "
            f"quality={self.quality_score}>"
        )
