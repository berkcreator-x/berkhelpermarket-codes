from __future__ import annotations

import asyncio
import datetime

from src.database import AsyncSessionLocal
from src.repositories import PaymentRepository
from src.utils import get_logger

logger = get_logger(__name__)

PAYMENT_TTL_HOURS = 24

CHECK_INTERVAL_SECONDS = 15 * 60  # раз в 15 минут


async def _expire_once() -> None:

    cutoff = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(hours=PAYMENT_TTL_HOURS)
    )

    async with AsyncSessionLocal() as session:

        payment_repo = PaymentRepository(session)

        expired = await payment_repo.expire_pending(cutoff)

        if expired:

            await session.commit()

            logger.info(
                "payments_expired",
                count=len(expired),
                labels=[p.label for p in expired],
            )

        else:

            logger.info(
                "payment_expiry_check_completed",
                expired_count=0,
            )


async def run_payment_expiry_loop() -> None:
    """
    Фоновая задача.

    Раз в CHECK_INTERVAL_SECONDS отменяет все платежи
    в статусе PENDING, созданные более PAYMENT_TTL_HOURS
    часов назад.

    Не начисляет и не списывает генерации —
    просто переводит "зависшие" ссылки на оплату
    в статус CANCELED, чтобы они больше не считались
    активными в истории покупок и не сбивали статистику.
    """

    logger.info(
        "payment_expiry_worker_started",
        ttl_hours=PAYMENT_TTL_HOURS,
        check_interval_seconds=CHECK_INTERVAL_SECONDS,
    )

    while True:

        try:
            await _expire_once()

        except Exception:
            logger.exception(
                "payment_expiry_loop_failed",
            )

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
