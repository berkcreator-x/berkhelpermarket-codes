from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from redis.asyncio import Redis

from src.bot import create_bot, create_dispatcher
from src.config import settings
from src.payments import register_webhook_routes
from src.utils import configure_logging, get_logger

logger = get_logger(__name__)

TELEGRAM_WEBHOOK_PATH = "/webhook/telegram"


async def on_startup(bot: Bot) -> None:
    if settings.webhook_base_url:
        webhook_url = f"{settings.webhook_base_url.rstrip('/')}{TELEGRAM_WEBHOOK_PATH}"
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        logger.info("telegram_webhook_set", url=webhook_url)
    else:
        logger.info("telegram_webhook_not_configured_using_polling")


async def on_shutdown(bot: Bot) -> None:
    if settings.webhook_base_url:
        await bot.delete_webhook()
    await bot.session.close()


async def run_webhook(bot: Bot, dispatcher: Dispatcher) -> None:
    """Run the bot in webhook mode behind an aiohttp web server.

    This is the recommended mode for free hosting platforms like Render,
    where the service must respond to HTTP requests (and may sleep between
    requests). Also serves the YooMoney payment webhook on the same app.
    """
    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    app = web.Application()

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="OK")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    register_webhook_routes(
        app=app,
        bot=bot,
    )

    SimpleRequestHandler(dispatcher=dispatcher, bot=bot).register(app, path=TELEGRAM_WEBHOOK_PATH)
    setup_application(app, dispatcher, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.web_server_host, port=settings.web_server_port)
    await site.start()

    logger.info(
        "webhook_server_started",
        host=settings.web_server_host,
        port=settings.web_server_port,
    )

    await asyncio.Event().wait()


async def run_polling(bot: Bot, dispatcher: Dispatcher) -> None:
    """Run the bot in long-polling mode (useful for local development)."""
    await on_startup(bot)
    logger.info("starting_polling")
    await dispatcher.start_polling(bot, on_shutdown=lambda bots: on_shutdown(bots[0]))


async def _close_httpx_clients() -> None:
    """
    Закрыть singleton httpx-клиенты.
    """

    import src.ai.proxyapi_client as proxy_module
    import src.payments.yoomoney_client as yoomoney_module

    if (
        hasattr(proxy_module, "_http_client")
        and proxy_module._http_client is not None
        and not proxy_module._http_client.is_closed
    ):
        await proxy_module._http_client.aclose()

    if (
        hasattr(yoomoney_module, "_http_client")
        and yoomoney_module._http_client is not None
        and not yoomoney_module._http_client.is_closed
    ):
        await yoomoney_module._http_client.aclose()


async def main() -> None:
    configure_logging()

    bot = create_bot()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    dispatcher = create_dispatcher(redis)

    try:
        if settings.webhook_base_url:
            await run_webhook(bot, dispatcher)
        else:
            await run_polling(bot, dispatcher)
    finally:
        await redis.aclose()
        await _close_httpx_clients()


if __name__ == "__main__":
    asyncio.run(main())
