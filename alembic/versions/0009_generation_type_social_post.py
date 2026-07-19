"""add 'social_post' value to generation_type enum

Revision ID: 0009_generation_type_social_post
Revises: 0008_generation_type_analysis
Create Date: 2026-07-18 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009_generation_type_social_post"
down_revision: str | None = "0008_generation_type_analysis"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE generation_type ADD VALUE IF NOT EXISTS 'social_post'"
    )


def downgrade() -> None:
    # PostgreSQL не поддерживает удаление значения из ENUM
    # напрямую. Значение остаётся в типе даже после отката —
    # это безопасно и не мешает работе приложения.
    pass
