from __future__ import annotations

from urllib.parse import urlencode

import httpx

from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)

YOOMONEY_QUICKPAY_URL = "https://yoomoney.ru/quickpay/confirm.xml"

_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=_TIMEOUT)
    return _http_client


class YooMoneyClient:
    """Генерация payment URL для YooMoney (без API проверки)."""

    def __init__(self) -> None:
        self._wallet = settings.yoomoney_wallet

    def build_payment_url(self, amount: float, label: str) -> str:
        params = {
            "receiver": self._wallet,
            "quickpay-form": "shop",
            "targets": "Покупка генераций BerkHelperMarket",
            "paymentType": "AC",
            "sum": f"{amount:.2f}",
            "label": label,
            "successURL": settings.payment_success_url,
        }
        return f"{YOOMONEY_QUICKPAY_URL}?{urlencode(params)}"


yoomoney_client = YooMoneyClient()
