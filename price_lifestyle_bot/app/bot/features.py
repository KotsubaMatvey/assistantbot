from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from aiogram import Router

from app.bot.handlers import admin, memory, settings, shopping, start


@dataclass(frozen=True)
class BotFeature:
    name: str
    routers: tuple[Router, ...]
    description: str
    enabled: bool = True


FEATURE_REGISTRY: tuple[BotFeature, ...] = (
    BotFeature("onboarding", (start.router,), "start/help commands"),
    BotFeature("settings", (settings.router,), "store and loyalty preferences"),
    BotFeature("memory", (memory.router,), "obsidian-backed user memory"),
    BotFeature("shopping", (shopping.router,), "basket parsing and price comparison"),
    BotFeature("admin", (admin.router,), "operator commands and scraping status"),
)


def enabled_routers() -> Iterable[Router]:
    for feature in FEATURE_REGISTRY:
        if feature.enabled:
            yield from feature.routers
