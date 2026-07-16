"""add 'canceled' value to payment_status enum

Revision ID: 0007_payment_status_canceled
Revises: 0006_generation_type_images
Create Date: 2026-07-16 21:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007_payment_status_canceled"
down_revision: str | None = "0006_generation_type_images"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    # Изначально (0001_initial) enum payment_status в БД был
    # создан только со значениями pending/paid/failed.
    # Значение "canceled" использовалось в Python-коде
    # (PaymentStatus.CANCELED) с самого начала, но никогда
    # не было добавлено в реальный Postgres-enum — из-за
    # этого воркер авто-отмены платежей падал с ошибкой
    # "invalid input value for enum payment_status: canceled".
    op.execute(
        "ALTER TYPE payment_status ADD VALUE IF NOT EXISTS 'canceled'"
    )


def downgrade() -> None:
    # PostgreSQL не поддерживает удаление значения из ENUM
    # напрямую. Значение остаётся в типе даже после отката —
    # это безопасно и не мешает работе приложения.
    pass
