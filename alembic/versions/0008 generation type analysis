"""add 'analysis' value to generation_type enum

Revision ID: 0008_generation_type_analysis
Revises: 0007_payment_status_canceled
Create Date: 2026-07-17 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_generation_type_analysis"
down_revision: str | None = "0007_payment_status_canceled"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE generation_type ADD VALUE IF NOT EXISTS 'analysis'"
    )


def downgrade() -> None:
    # PostgreSQL не поддерживает удаление значения из ENUM
    # напрямую. Значение остаётся в типе даже после отката —
    # это безопасно и не мешает работе приложения.
    pass
