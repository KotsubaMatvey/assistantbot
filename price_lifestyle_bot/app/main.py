from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.config import Settings, get_settings
from app.logging_config import configure_logging, get_logger

if TYPE_CHECKING:
    from aiogram import Bot

logger = get_logger(__name__)


async def main() -> None:
    configure_logging()
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    from aiogram import Bot

    bot = Bot(token=settings.bot_token)
    from app.bot.dispatcher import create_dispatcher
    from app.services.scheduler import create_scheduler

    dispatcher = create_dispatcher()
    scheduler = create_scheduler(bot=bot)
    if settings.mini_app_api_enabled:
        from app.services.mini_app_server import MiniAppHttpServer

        mini_app_server = MiniAppHttpServer(settings)
    else:
        mini_app_server = None
    menu_task: asyncio.Task[None] | None = None
    if mini_app_server is not None:
        await mini_app_server.start()
    scheduler.start()
    menu_task = asyncio.create_task(_configure_bot_menu(bot, settings))
    logger.info("bot_started", city=settings.city)
    try:
        await dispatcher.start_polling(bot)
    finally:
        if menu_task is not None:
            await menu_task
        scheduler.shutdown(wait=False)
        if mini_app_server is not None:
            await mini_app_server.stop()
        await bot.session.close()
        from app.db.session import dispose_engine

        await dispose_engine()


async def _configure_bot_menu(bot: Bot, settings: Settings) -> None:
    try:
        from app.bot.menu import configure_bot_menu

        await configure_bot_menu(bot, settings)
    except Exception as exc:
        logger.warning("bot_menu_config_failed", error=str(exc))


if __name__ == "__main__":
    asyncio.run(main())
