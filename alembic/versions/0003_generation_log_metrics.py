"""add generation log metrics

Revision ID: 0003_generation_log_metrics
Revises: 0002_check_balance
Create Date: 2026-07-11 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_generation_log_metrics"
down_revision: str | None = "0002_check_balance"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column(
        "generation_logs",
        sa.Column(
            "cost",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "generation_logs",
        sa.Column(
            "quality_score",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "generation_logs",
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "generation_logs",
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="success",
        ),
    )


def downgrade() -> None:
    op.drop_column("generation_logs", "status")
    op.drop_column("generation_logs", "duration_ms")
    op.drop_column("generation_logs", "quality_score")
    op.drop_column("generation_logs", "cost")
