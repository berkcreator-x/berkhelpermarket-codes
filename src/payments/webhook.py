from __future__ import annotations

import time
import hashlib
import hmac
from aiohttp import web

from src.config import settings
from src.database import AsyncSessionLocal
from src.payments.payment_service import PaymentService
from src.repositories import PaymentRepository, UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

YOOMONEY_WEBHOOK_PATH = "/webhook/yoomoney"

# защита от повторных webhook (in-memory, можно заменить Redis позже)
_PROCESSED_LABELS: dict[str, float] = {}
_LABEL_TTL_SECONDS = 60 * 10  # 10 минут


# =========================
# SECURITY LAYER
# =========================

def _is_valid_signature(data: dict[str, str]) -> bool:
    """Проверка подписи YooMoney (sha1)."""

    if not settings.yoomoney_secret:
        logger.warning("yoomoney_secret_not_set")
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

    expected = hashlib.sha1(source.encode("utf-8")).hexdigest()
    return hmac.compare_digest(expected, data.get("sha1_hash", ""))


def _is_duplicate(label: str) -> bool:
    now = time.time()

    # cleanup TTL
    expired = [k for k, v in _PROCESSED_LABELS.items() if now - v > _LABEL_TTL_SECONDS]
    for k in expired:
        _PROCESSED_LABELS.pop(k, None)

    if label in _PROCESSED_LABELS:
        return True

    _PROCESSED_LABELS[label] = now
    return False


def _is_valid_payload(data: dict[str, str]) -> bool:
    """Базовая проверка webhook payload."""

    if data.get("notification_type") != "p2p-incoming":
        return False

    if not data.get("label"):
        return False

    if data.get("currency") != "643":
        return False

    if data.get("receiver") != settings.yoomoney_wallet:
        return False

    return True


# =========================
# WEBHOOK HANDLER
# =========================

async def yoomoney_webhook_handler(request: web.Request) -> web.Response:
    start_time = time.time()

    try:
        data = dict(await request.post())
    except Exception as exc:
        logger.error("webhook_parse_error", error=str(exc))
        return web.Response(status=400, text="bad request")

    label = data.get("label", "")

    logger.info(
        "webhook_received",
        label=label,
        ip=request.remote,
        user_agent=request.headers.get("User-Agent"),
        amount=data.get("amount"),
    )

    # 1. payload validation
    if not _is_valid_payload(data):
        logger.warning("webhook_invalid_payload", label=label)
        return web.Response(status=400, text="invalid payload")

    # 2. signature validation
    if not _is_valid_signature(data):
        logger.warning("webhook_invalid_signature", label=label)
        return web.Response(status=400, text="invalid signature")

    # 3. duplicate protection
    if _is_duplicate(label):
        logger.info("webhook_duplicate", label=label)
        return web.Response(status=200, text="duplicate ignored")

    # 4. business logic
    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        payment_repo = PaymentRepository(session)

        service = PaymentService(
            session=session,
            user_repo=user_repo,
            payment_repo=payment_repo,
        )

        payment = await service.confirm_payment_by_label(label)

        if payment is None:
            await session.rollback()
        else:
            await session.commit()

    logger.info(
        "webhook_processed",
        label=label,
        duration_ms=int((time.time() - start_time) * 1000),
    )

    return web.Response(status=200, text="OK")


def register_webhook_routes(app: web.Application) -> None:
    app.router.add_post(YOOMONEY_WEBHOOK_PATH, yoomoney_webhook_handler)
