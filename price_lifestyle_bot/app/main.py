from __future__ import annotations

import asyncio

from aiogram import Bot

from app.bot.dispatcher import create_dispatcher
from app.bot.menu import configure_bot_menu
from app.config import get_settings
from app.db.session import dispose_engine
from app.logging_config import configure_logging, get_logger
from app.services.mini_app_server import MiniAppHttpServer
from app.services.scheduler import create_scheduler

logger = get_logger(__name__)


async def main() -> None:
    configure_logging()
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    bot = Bot(token=settings.bot_token)
    dispatcher = create_dispatcher()
    scheduler = create_scheduler(bot=bot)
    mini_app_server = MiniAppHttpServer(settings)
    await mini_app_server.start()
    scheduler.start()
    await configure_bot_menu(bot, settings)
    logger.info("bot_started", city=settings.city)
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await mini_app_server.stop()
        await bot.session.close()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
