from __future__ import annotations

import hashlib
import hmac

from aiohttp import web

from src.config import settings
from src.database import AsyncSessionLocal
from src.payments.payment_service import PaymentService
from src.repositories import PaymentRepository, UserRepository
from src.utils import get_logger

logger = get_logger(__name__)

YOOMONEY_NOTIFICATION_PATH = "/webhook/yoomoney"


def _verify_signature(data: dict[str, str]) -> bool:
    """Verify the YooMoney notification signature (sha1_hash).

    See: https://yoomoney.ru/docs/wallet/using-api/notification-p2p-incoming
    """
    if not settings.yoomoney_secret:
        # No secret configured → skip strict verification.
        # Acceptable only during initial setup; set YOOMONEY_SECRET in production.
        logger.warning("yoomoney_webhook_no_secret_configured")
        return True

    fields = [
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
    source = "&".join(fields)
    expected = hashlib.sha1(source.encode("utf-8")).hexdigest()
    # Timing-safe comparison to prevent timing attacks
    return hmac.compare_digest(expected, data.get("sha1_hash", ""))


async def yoomoney_webhook_handler(request: web.Request) -> web.Response:
    """Handle YooMoney HTTP notification (P2P incoming payment).

    Stateless and resilient: validates signature, then confirms the payment
    via the PaymentService, which is idempotent.
    """
    try:
        data = dict(await request.post())
    except Exception as exc:  # noqa: BLE001
        logger.error("yoomoney_webhook_bad_request", error=str(exc))
        return web.Response(status=400, text="bad request")

    if not _verify_signature(data):
        logger.warning("yoomoney_webhook_invalid_signature", label=data.get("label"))
        return web.Response(status=400, text="invalid signature")

    label = data.get("label")
    if not label:
        return web.Response(status=400, text="missing label")

    logger.info(
        "yoomoney_webhook_received",
        label=label,
        amount=data.get("amount"),
        operation_id=data.get("operation_id"),
        notification_type=data.get("notification_type"),
    )

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        payment_repo = PaymentRepository(session)
        payment_service = PaymentService(user_repo, payment_repo)

        payment = await payment_service.confirm_payment_by_label(label)
        if payment is not None:
            await session.commit()
        else:
            await session.rollback()

    return web.Response(status=200, text="OK")


def register_webhook_routes(app: web.Application) -> None:
    app.router.add_post(YOOMONEY_NOTIFICATION_PATH, yoomoney_webhook_handler)
