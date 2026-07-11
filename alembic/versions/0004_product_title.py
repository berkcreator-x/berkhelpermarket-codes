"""add product_title to generation_logs

Revision ID: 0004_product_title
Revises: 0003_generation_log_metrics
Create Date: 2026-07-11 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_product_title"
down_revision: str | None = "0003_generation_log_metrics"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column(
        "generation_logs",
        sa.Column(
            "product_title",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("generation_logs", "product_title")
