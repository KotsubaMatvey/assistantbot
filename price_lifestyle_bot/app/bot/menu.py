from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import MenuButtonCommands, MenuButtonWebApp, WebAppInfo

from app.bot.commands import public_bot_commands
from app.bot.feature_flags import is_feature_enabled
from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.services.mini_app import mini_app_manifest

logger = get_logger(__name__)


async def configure_bot_menu(bot: Bot, settings: Settings | None = None) -> None:
    runtime_settings = settings or get_settings()
    await bot.set_my_commands(public_bot_commands())

    manifest = mini_app_manifest(runtime_settings.tg_mini_app_url)
    menu_button: MenuButtonWebApp | MenuButtonCommands
    if manifest.enabled and is_feature_enabled("miniapp", runtime_settings):
        menu_button = MenuButtonWebApp(
            text="Mini App",
            web_app=WebAppInfo(url=manifest.url),
        )
    else:
        menu_button = MenuButtonCommands()

    try:
        await bot.set_chat_menu_button(menu_button=menu_button)
    except TelegramBadRequest as exc:
        logger.warning("bot_menu_button_failed", error=str(exc))
