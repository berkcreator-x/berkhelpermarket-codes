"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-13 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    plan_type_enum = sa.Enum("free", "pro", name="plan_type")
    generation_type_enum = sa.Enum("new", "improve", name="generation_type")
    payment_status_enum = sa.Enum("pending", "paid", "failed", name="payment_status")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("plan", plan_type_enum, nullable=False, server_default="free"),
        sa.Column("generation_balance", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "generation_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", generation_type_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_generation_logs_user_id", "generation_logs", ["user_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("generations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", payment_status_enum, nullable=False, server_default="pending"),
        sa.Column("payment_id", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_payments_payment_id", "payments", ["payment_id"], unique=True)
    op.create_index("ix_payments_label", "payments", ["label"], unique=True)
    op.create_index("ix_payments_user_id", "payments", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_index("ix_payments_label", table_name="payments")
    op.drop_index("ix_payments_payment_id", table_name="payments")
    op.drop_table("payments")

    op.drop_index("ix_generation_logs_user_id", table_name="generation_logs")
    op.drop_table("generation_logs")

    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")

    sa.Enum(name="payment_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="generation_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="plan_type").drop(op.get_bind(), checkfirst=True)
