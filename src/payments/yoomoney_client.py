from __future__ import annotations

from urllib.parse import urlencode

import httpx

from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)

YOOMONEY_QUICKPAY_URL = "https://yoomoney.ru/quickpay/confirm.xml"
YOOMONEY_API_OPERATION_HISTORY_URL = "https://yoomoney.ru/api/operation-history"

_TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=30.0,
    write=10.0,
    pool=5.0,
)

# Singleton httpx client
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client

    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
        )

    return _http_client


class YooMoneyClient:
    """
    Клиент YooMoney.

    Отвечает только за:

    • генерацию ссылки оплаты

    • проверку оплаты через API

    Не содержит бизнес-логики.
    """

    def __init__(self) -> None:
        self._token = settings.yoomoney_token
        self._wallet = settings.yoomoney_wallet

    def build_payment_url(
        self,
        amount: float,
        label: str,
    ) -> str:
        params = {
            "receiver": self._wallet,
            "quickpay-form": "shop",
            "targets": "Покупка генераций BerkHelperMarket",
            "paymentType": "AC",
            "sum": f"{amount:.2f}",
            "label": label,
            "successURL": settings.payment_success_url,
        }

        return (
            f"{YOOMONEY_QUICKPAY_URL}"
            f"?{urlencode(params)}"
        )

    async def verify_payment(
        self,
        label: str,
    ) -> bool:
        """
        Проверка оплаты через operation-history API.

        Возвращает True только если операция успешно завершена.
        """

        if not self._token:
            logger.error("yoomoney_token_not_configured")
            return False

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "label": label,
            "records": "10",
        }

        try:
            client = _get_http_client()

            response = await client.post(
                YOOMONEY_API_OPERATION_HISTORY_URL,
                headers=headers,
                data=data,
            )

        except httpx.TimeoutException:
            logger.exception(
                "yoomoney_timeout",
                label=label,
            )
            return False

        except httpx.RequestError:
            logger.exception(
                "yoomoney_network_error",
                label=label,
            )
            return False

        if response.status_code == 401:
            logger.error(
                "yoomoney_unauthorized",
            )
            return False

        if response.status_code != 200:
            logger.error(
                "yoomoney_bad_response",
                status=response.status_code,
                label=label,
                body=response.text[:300],
            )
            return False

        try:
            payload = response.json()

        except ValueError:
            logger.exception(
                "yoomoney_invalid_json",
                label=label,
            )
            return False

        operations = payload.get(
            "operations",
            [],
        )

        for operation in operations:

            if (
                operation.get("label") == label
                and operation.get("status") == "success"
            ):
                logger.info(
                    "payment_verified",
                    label=label,
                    operation_id=operation.get("operation_id"),
                    amount=operation.get("amount"),
                )
                return True

        logger.info(
            "payment_not_found",
            label=label,
        )

        return False


yoomoney_client = YooMoneyClient()
