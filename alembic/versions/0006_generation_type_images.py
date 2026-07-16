"""add 'images' value to generation_type enum

Revision ID: 0006_generation_type_images
Revises: 0005_payment_enhancements
Create Date: 2026-07-16 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_generation_type_images"
down_revision: str | None = "0005_payment_enhancements"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE generation_type ADD VALUE IF NOT EXISTS 'images'"
    )


def downgrade() -> None:
    # PostgreSQL не поддерживает удаление значения из ENUM
    # напрямую (ALTER TYPE ... DROP VALUE отсутствует).
    # Значение 'images' остаётся в типе generation_type
    # даже после отката миграции — это безопасно и не
    # мешает работе приложения.
    pass
