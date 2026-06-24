from __future__ import annotations

from urllib.parse import urlencode

import httpx

from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)

YOOMONEY_QUICKPAY_URL = "https://yoomoney.ru/quickpay/confirm.xml"
YOOMONEY_API_OPERATION_HISTORY_URL = "https://yoomoney.ru/api/operation-history"

_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)

# Singleton httpx client для переиспользования соединений
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=_TIMEOUT)
    return _http_client


class YooMoneyClient:
    """Клиент ЮMoney: генерация ссылки quickpay и проверка оплаты через API."""

    def __init__(self) -> None:
        self._token = settings.yoomoney_token
        self._wallet = settings.yoomoney_wallet

    def build_payment_url(self, amount: float, label: str) -> str:
        """Сформировать quickpay-ссылку для перевода на кошелёк."""
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

    async def verify_payment(self, label: str) -> bool:
        """Проверить через operation-history API что платёж с данным label прошёл.

        Возвращает True если найдена операция со статусом success.
        """
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"label": label, "records": "10"}

        try:
            client = _get_http_client()
            response = await client.post(
                YOOMONEY_API_OPERATION_HISTORY_URL,
                headers=headers,
                data=data,
            )
        except httpx.TimeoutException as exc:
            logger.error("yoomoney_verify_timeout", label=label, error=str(exc))
            return False
        except httpx.RequestError as exc:
            logger.error("yoomoney_verify_network_error", label=label, error=str(exc))
            return False

        if response.status_code == 401:
            logger.error("yoomoney_verify_unauthorized", label=label)
            return False

        if response.status_code != 200:
            logger.error(
                "yoomoney_verify_bad_status",
                label=label,
                status=response.status_code,
                body=response.text[:300],
            )
            return False

        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("yoomoney_verify_parse_error", label=label, error=str(exc))
            return False

        for operation in payload.get("operations", []):
            if operation.get("label") == label and operation.get("status") == "success":
                logger.info(
                    "yoomoney_payment_verified",
                    label=label,
                    operation_id=operation.get("operation_id"),
                    amount=operation.get("amount"),
                )
                return True

        return False


yoomoney_client = YooMoneyClient()
