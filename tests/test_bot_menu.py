from __future__ import annotations

import asyncio
from typing import Any

from aiogram.types import MenuButtonCommands, MenuButtonWebApp
from app.bot.menu import configure_bot_menu
from app.config import Settings


class FakeBot:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.menu_button: object | None = None

    async def set_my_commands(self, commands: list[Any]) -> bool:
        self.commands = [str(command.command) for command in commands]
        return True

    async def set_chat_menu_button(self, menu_button: object) -> bool:
        self.menu_button = menu_button
        return True


def test_configure_bot_menu_sets_mini_app_button_when_url_is_configured() -> None:
    bot = FakeBot()
    settings = Settings(tg_mini_app_url="https://example.com/app")

    asyncio.run(configure_bot_menu(bot, settings))

    assert bot.commands == ["start", "help"]
    assert isinstance(bot.menu_button, MenuButtonWebApp)
    assert bot.menu_button.web_app.url == "https://example.com/app"


def test_configure_bot_menu_uses_commands_button_without_mini_app_url() -> None:
    bot = FakeBot()
    settings = Settings(tg_mini_app_url="")

    asyncio.run(configure_bot_menu(bot, settings))

    assert bot.commands == ["start", "help"]
    assert isinstance(bot.menu_button, MenuButtonCommands)


def test_configure_bot_menu_uses_commands_button_when_mini_app_feature_is_disabled() -> None:
    bot = FakeBot()
    settings = Settings(
        tg_mini_app_url="https://example.com/app",
        bot_disabled_features=["miniapp"],
    )

    asyncio.run(configure_bot_menu(bot, settings))

    assert isinstance(bot.menu_button, MenuButtonCommands)
