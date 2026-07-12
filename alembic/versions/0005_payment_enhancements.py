"""payment enhancements: order_number, source, provider_transaction_id, paid_at

Revision ID: 0005_payment_enhancements
Revises: 0004_product_title
Create Date: 2026-07-12 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_payment_enhancements"
down_revision: str | None = "0004_product_title"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:

    # =====================================================
    # order_number — человекочитаемый номер заказа
    # =====================================================

    op.execute(
        "CREATE SEQUENCE IF NOT EXISTS payment_order_seq "
        "START WITH 1000"
    )

    op.add_column(
        "payments",
        sa.Column(
            "order_number",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Бэкфилл для уже существующих строк —
    # каждой присваиваем следующее значение из последовательности.
    op.execute(
        "UPDATE payments "
        "SET order_number = nextval('payment_order_seq') "
        "WHERE order_number IS NULL"
    )

    op.alter_column(
        "payments",
        "order_number",
        nullable=False,
        server_default=sa.text("nextval('payment_order_seq')"),
    )

    op.create_unique_constraint(
        "uq_payments_order_number",
        "payments",
        ["order_number"],
    )

    op.create_index(
        "ix_payments_order_number",
        "payments",
        ["order_number"],
    )

    op.execute(
        "ALTER SEQUENCE payment_order_seq "
        "OWNED BY payments.order_number"
    )

    # =====================================================
    # source — источник/провайдер оплаты
    # =====================================================

    op.add_column(
        "payments",
        sa.Column(
            "source",
            sa.String(length=50),
            nullable=False,
            server_default="yoomoney",
        ),
    )

    # =====================================================
    # provider_transaction_id — номер операции у провайдера
    # (у YooMoney это operation_id из вебхука)
    # =====================================================

    op.add_column(
        "payments",
        sa.Column(
            "provider_transaction_id",
            sa.String(length=255),
            nullable=True,
        ),
    )

    # =====================================================
    # paid_at — момент фактической оплаты
    # =====================================================

    op.add_column(
        "payments",
        sa.Column(
            "paid_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Бэкфилл: для уже оплаченных платежей используем
    # updated_at как лучшую доступную оценку момента оплаты.
    op.execute(
        "UPDATE payments "
        "SET paid_at = updated_at "
        "WHERE status = 'paid' AND paid_at IS NULL"
    )


def downgrade() -> None:

    op.drop_column("payments", "paid_at")
    op.drop_column("payments", "provider_transaction_id")
    op.drop_column("payments", "source")

    op.drop_index("ix_payments_order_number", table_name="payments")
    op.drop_constraint(
        "uq_payments_order_number", "payments", type_="unique"
    )
    op.drop_column("payments", "order_number")
    op.execute("DROP SEQUENCE IF EXISTS payment_order_seq")
