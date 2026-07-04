from urllib.parse import urlencode

import httpx

from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)


YOOMONEY_QUICKPAY_URL = "https://yoomoney.ru/quickpay/confirm.xml"

_http_client: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http_client

    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30)

    return _http_client


class YooMoneyClient:
    def __init__(self) -> None:
        self.wallet = settings.yoomoney_wallet

    def build_payment_url(self, amount: float, label: str) -> str:
        params = {
            "receiver": self.wallet,
            "quickpay-form": "shop",
            "targets": "BerkHelperMarket",
            "paymentType": "AC",
            "sum": f"{amount:.2f}",
            "label": label,
        }

        return f"{YOOMONEY_QUICKPAY_URL}?{urlencode(params)}"

    async def verify_payment(self, label: str) -> bool:
        """
        MVP-версия: пока считаем webhook источником истины.
        """
        return True


yoomoney_client = YooMoneyClient()
