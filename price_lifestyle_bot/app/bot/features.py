from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from aiogram import Router

from app.bot.feature_flags import enabled_feature_names
from app.bot.handlers import admin, lifestyle, markets, memory, miniapp, settings, shopping, start


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
    BotFeature("lifestyle", (lifestyle.router,), "daily brief, pantry, budget, alerts"),
    BotFeature("markets", (markets.router,), "global market watch"),
    BotFeature("miniapp", (miniapp.router,), "Telegram Mini App payloads"),
    BotFeature("shopping", (shopping.router,), "basket parsing and price comparison"),
    BotFeature("admin", (admin.router,), "operator commands and scraping status"),
)


def enabled_routers() -> Iterable[Router]:
    enabled = set(enabled_feature_names())
    for feature in FEATURE_REGISTRY:
        if feature.name in enabled:
            yield from feature.routers
