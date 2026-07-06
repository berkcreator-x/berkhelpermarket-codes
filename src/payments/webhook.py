from __future__ import annotations

import hashlib
import hmac
import time

from aiogram import Bot
from aiohttp import web

from src.config import settings
from src.database import AsyncSessionLocal
from src.payments.payment_service import PaymentService
from src.repositories import (
    PaymentRepository,
    UserRepository,
)
from src.utils import get_logger

logger = get_logger(__name__)

YOOMONEY_WEBHOOK_PATH = "/webhook/yoomoney"

# =====================================================
# Anti-spam cache
# Не влияет на начисление генераций.
# Главная защита находится в PaymentService.
# =====================================================

_PROCESSED_LABELS: dict[str, float] = {}

_LABEL_TTL_SECONDS = 600

_bot: Bot | None = None


# =====================================================
# SECURITY
# =====================================================

def _is_valid_signature(
    data: dict[str, str],
) -> bool:

    if not settings.yoomoney_secret:
        logger.error(
            "yoomoney_secret_not_configured",
        )
        return False

    source = "&".join([
        data.get("notification_type", ""),
        data.get("operation_id", ""),
        data.get("amount", ""),
        data.get("currency", ""),
        data.get("datetime", ""),
        data.get("sender", ""),
        data.get("codepro", ""),
        settings.yoomoney_secret,
        data.get("label", ""),
    ])

    expected = hashlib.sha1(
        source.encode("utf-8"),
    ).hexdigest()

    return hmac.compare_digest(
        expected,
        data.get("sha1_hash", ""),
    )


def _cleanup_cache() -> None:

    now = time.time()

    expired = [
        key
        for key, created in _PROCESSED_LABELS.items()
        if now - created > _LABEL_TTL_SECONDS
    ]

    for key in expired:
        _PROCESSED_LABELS.pop(
            key,
            None,
        )


def _is_duplicate(
    label: str,
) -> bool:

    _cleanup_cache()

    if label in _PROCESSED_LABELS:
        return True

    _PROCESSED_LABELS[label] = time.time()

    return False


def _is_valid_payload(
    data: dict[str, str],
) -> bool:

    return (
        data.get("notification_type") == "p2p-incoming"
        and data.get("currency") == "643"
        and data.get("receiver") == settings.yoomoney_wallet
        and bool(data.get("label"))
    )


# =====================================================
# WEBHOOK
# =====================================================

async def yoomoney_webhook_handler(
    request: web.Request,
) -> web.Response:

    started = time.perf_counter()

    try:
        data = dict(
            await request.post()
        )

    except Exception:

        logger.exception(
            "webhook_parse_failed",
        )

        return web.Response(
            status=400,
            text="bad request",
        )

    label = data.get(
        "label",
        "",
    )

    logger.info(
        "webhook_received",
        label=label,
        amount=data.get("amount"),
        sender=data.get("sender"),
        ip=request.remote,
    )

    if not _is_valid_payload(data):

        logger.warning(
            "webhook_invalid_payload",
            label=label,
        )

        return web.Response(
            status=400,
            text="invalid payload",
        )

    if not _is_valid_signature(data):

        logger.warning(
            "webhook_invalid_signature",
            label=label,
        )

        return web.Response(
            status=400,
            text="invalid signature",
        )

    # Это только защита от спама.
    # Даже если убрать этот кэш,
    # PaymentService всё равно
    # не начислит генерации дважды.

    if _is_duplicate(label):

        logger.info(
            "duplicate_webhook",
            label=label,
        )

        return web.Response(
            status=200,
            text="duplicate",
        )

    async with AsyncSessionLocal() as session:

        service = PaymentService(
            session=session,
            user_repo=UserRepository(session),
            payment_repo=PaymentRepository(session),
        )

        payment = await service.confirm_payment_by_label(
            label,
        )

        if payment is None:

            logger.info(
                "payment_not_confirmed",
                label=label,
            )

        else:

            if _bot is not None:

                user = await UserRepository(session).get_by_id(
                    payment.user_id,
                )

                if user is not None:

try:

                        await _bot.send_message(
                            chat_id=user.telegram_id,
                            text=(
                                "🎉 <b>Оплата получена!</b>\n\n"
                                f"На ваш баланс начислено "
                                f"<b>{payment.generations}</b> генераций.\n\n"
                                f"💎 Баланс: "
                                f"<b>{user.generation_balance}</b> генераций.\n\n"
                                "Спасибо за покупку ❤️"
                            ),
                        )

                    except Exception:

                        logger.exception(
                            "payment_notification_failed",
                            user_id=user.id,
                        )
