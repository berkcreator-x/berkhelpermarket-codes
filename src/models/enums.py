from __future__ import annotations

import enum


class PlanType(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"


class GenerationType(str, enum.Enum):
    NEW = "new"
    IMPROVE = "improve"
    ANALYSIS = "analysis"
    # IMAGES: фича удалена (нестабильное качество, высокая
    # себестоимость). Значение оставлено в enum ТОЛЬКО ради
    # совместимости со старыми записями в БД — новых
    # генераций этого типа больше не создаётся нигде в коде.
    IMAGES = "images"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELED = "canceled"
