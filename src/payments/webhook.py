from __future__ import annotations

import hashlib
import hmac
import time

from aiohttp import web

from src.config import settings
from src.database import AsyncSessionLocal
from src.payments.payment_service import PaymentService
from src.repositories import PaymentRepository, UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

YOOMONEY_WEBHOOK_PATH = "/webhook/yoomoney"

# Защита от шквала одинаковых webhook.
# Основная защита всё равно находится внутри PaymentService
# через PaymentStatus.PAID + SELECT FOR UPDATE.
_PROCESSED_LABELS: dict[str, float] = {}
_LABEL_TTL_SECONDS = 600


# =====================================================
# SECURITY
# =====================================================

def _is_valid_signature(data: dict[str, str]) -> bool:
    if not settings.yoomoney_secret:
        logger.error("yoomoney_secret_not_configured")
        return False

    source = "&".join(
        [
            data.get("notification_type", ""),
            data.get("operation_id", ""),
            data.get("amount", ""),
            data.get("currency", ""),
            data.get("datetime", ""),
            data.get("sender", ""),
            data.get("codepro", ""),
            settings.yoomoney_secret,
            data.get("label", ""),
        ]
    )

    expected = hashlib.sha1(
        source.encode("utf-8")
    ).hexdigest()

    return hmac.compare_digest(
        expected,
        data.get("sha1_hash", ""),
    )


def _cleanup_cache() -> None:
    now = time.time()

    expired = [
        label
        for label, created in _PROCESSED_LABELS.items()
        if now - created > _LABEL_TTL_SECONDS
    ]

    for label in expired:
        _PROCESSED_LABELS.pop(label, None)


def _is_duplicate(label: str) -> bool:
    _cleanup_cache()

    if label in _PROCESSED_LABELS:
        return True

    _PROCESSED_LABELS[label] = time.time()
    return False


def _is_valid_payload(data: dict[str, str]) -> bool:
    return (
        data.get("notification_type") == "p2p-incoming"
        and bool(data.get("label"))
        and data.get("currency") == "643"
        and data.get("receiver") == settings.yoomoney_wallet
    )


# =====================================================
# WEBHOOK
# =====================================================

async def yoomoney_webhook_handler(
    request: web.Request,
) -> web.Response:

    started = time.perf_counter()

    try:
        data = dict(await request.post())
    except Exception:
        logger.exception("webhook_parse_failed")
        return web.Response(
            status=400,
            text="bad request",
        )

    label = data.get("label", "")

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

        user_repo = UserRepository(session)
        payment_repo = PaymentRepository(session)

        service = PaymentService(
            session=session,
            user_repo=user_repo,
            payment_repo=payment_repo,
        )

        payment = await service.confirm_payment_by_label(
            label
        )

        if payment is None:
            return web.Response(
                status=200,
                text="not confirmed",
            )

        user = await user_repo.get_by_id(
            payment.user_id,
        )

        if user is None:
            logger.error(
                "payment_user_not_found_after_confirmation",
                payment_id=payment.id,
                user_id=payment.user_id,
            )
            return web.Response(
                status=200,
                text="user missing",
            )

        # Здесь в будущем будет:
        #
        # await bot.send_message(...)
        #
        # Сейчас архитектура уже готова —
        # осталось только получить экземпляр Bot.

    logger.info(
        "webhook_processed",
        label=label,
        duration_ms=round(
            (time.perf_counter() - started) * 1000
        ),
    )

    return web.Response(
        status=200,
        text="OK",
    )


def register_webhook_routes(
    app: web.Application,
) -> None:
    app.router.add_post(
        YOOMONEY_WEBHOOK_PATH,
        yoomoney_webhook_handler,
    )
