from __future__ import annotations

import enum


class PlanType(str, enum.Enum):
    FREE = "free"
    PRO = "pro"


class GenerationType(str, enum.Enum):
    NEW = "new"
    IMPROVE = "improve"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
