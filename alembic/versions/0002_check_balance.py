"""add check balance gte zero

Revision ID: 0002_check_balance
Revises: 0001_initial
Create Date: 2026-06-16 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_check_balance"
down_revision: str | None = "0001_initial"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    # CHECK constraint: баланс не может быть отрицательным на уровне БД
    op.create_check_constraint(
        "ck_users_balance_non_negative",
        "users",
        "generation_balance >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_users_balance_non_negative",
        "users",
        type_="check",
    )
