from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Telegram ──────────────────────────────────────────────────────────────
    bot_token: str
    admin_id: int

    # ── Database ──────────────────────────────────────────────────────────────
    # postgresql+asyncpg://user:pass@host:5432/dbname
    database_url: str

    # ── Redis ─────────────────────────────────────────────────────────────────
    # redis://host:6379/0  (Render Redis / Upstash)
    redis_url: str

    # ── ProxyAPI (OpenAI-compatible, работает из РФ) ──────────────────────────
    proxyapi_api_key: str
    proxyapi_base_url: str = "https://api.proxyapi.ru/openai/v1"
    ai_model: str = "gpt-4o-mini"

    # ── YooMoney ──────────────────────────────────────────────────────────────
    yoomoney_wallet: str
    yoomoney_token: str
    # Секрет HTTP-уведомлений: настроить в кабинете ЮMoney.
    # None допустимо только в dev-окружении — в production ОБЯЗАТЕЛЕН.
    yoomoney_secret: str | None = None
    # URL куда перенаправить пользователя после оплаты
    payment_success_url: str = "https://t.me/BerkHelperMarketBot"

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit_messages: int = 5
    rate_limit_period_seconds: int = 10

    # ── App / Render ──────────────────────────────────────────────────────────
    # Пустое → long-polling (локально). Заполнить для Render webhook-режима.
    webhook_base_url: str | None = None
    web_server_host: str = "0.0.0.0"
    web_server_port: int = 8080
    log_level: str = "INFO"


settings = Settings()  # type: ignore[call-arg]
