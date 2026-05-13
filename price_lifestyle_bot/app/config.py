from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, field_validator

load_dotenv: Any
try:
    from dotenv import load_dotenv as load_dotenv
except ImportError:
    load_dotenv = None

try:
    from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
except ImportError:
    from pydantic import BaseModel as BaseSettings  # type: ignore[assignment]

    class NoDecode:  # type: ignore[no-redef]
        pass

    def SettingsConfigDict(**kwargs: object) -> dict[str, object]:  # type: ignore[no-redef]
        return kwargs


class Settings(BaseSettings):
    bot_token: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pricebot"
    redis_url: str = "redis://localhost:6379/0"
    env: str = "local"
    city: str = "Бор"
    timezone: str = "Europe/Moscow"
    price_freshness_hours: int = 24
    scrape_interval_hours: int = 12
    enable_playwright: bool = False
    obsidian_vault_path: str = "assistantbotmemory"
    assistant_access_mode: str = "pairing"
    assistant_approval_ttl_minutes: int = 30
    assistant_pairing_ttl_minutes: int = 15
    assistant_context_visibility: str = "allowlist"
    assistant_group_trigger_policy: str = "mention"
    assistant_default_mode: str = "secretary"
    tg_mini_app_url: str = ""
    bot_enabled_features: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["all"]
    )
    bot_disabled_features: Annotated[list[str], NoDecode] = Field(default_factory=list)
    live_price_refresh_enabled: bool = False
    live_price_refresh_limit_per_query: int = 10
    admin_telegram_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)

    magnit_shop_code: str | None = None
    magnit_shop_type: str | None = None
    pyaterochka_store_id: str | None = None
    pyaterochka_city_id: str | None = None
    spar_region: str | None = None
    smart_store_id: str | None = None
    fix_price_city: str | None = None

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def parse_admin_telegram_ids(cls, value: object) -> list[int] | object:
        if isinstance(value, str):
            return _parse_admin_telegram_ids(value)
        return value

    @field_validator("bot_enabled_features", "bot_disabled_features", mode="before")
    @classmethod
    def parse_feature_names(cls, value: object) -> list[str] | object:
        if isinstance(value, str):
            return _parse_feature_names(value)
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **data: object) -> None:
        if load_dotenv is not None:
            load_dotenv()
        if "admin_telegram_ids" not in data:
            admin_ids = os.getenv("ADMIN_TELEGRAM_IDS")
            if admin_ids is not None:
                data["admin_telegram_ids"] = _parse_admin_telegram_ids(admin_ids)
        if BaseSettings.__module__.startswith("pydantic."):
            env_data = {
                "bot_token": os.getenv("BOT_TOKEN", ""),
                "database_url": os.getenv(
                    "DATABASE_URL",
                    "postgresql+asyncpg://postgres:postgres@localhost:5432/pricebot",
                ),
                "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                "env": os.getenv("ENV", "local"),
                "city": os.getenv("CITY", "Бор"),
                "price_freshness_hours": int(os.getenv("PRICE_FRESHNESS_HOURS", "24")),
                "scrape_interval_hours": int(os.getenv("SCRAPE_INTERVAL_HOURS", "12")),
                "enable_playwright": os.getenv("ENABLE_PLAYWRIGHT", "false").lower() == "true",
                "obsidian_vault_path": os.getenv("OBSIDIAN_VAULT_PATH", "assistantbotmemory"),
                "assistant_access_mode": os.getenv("ASSISTANT_ACCESS_MODE", "pairing"),
                "assistant_approval_ttl_minutes": int(
                    os.getenv("ASSISTANT_APPROVAL_TTL_MINUTES", "30")
                ),
                "assistant_pairing_ttl_minutes": int(
                    os.getenv("ASSISTANT_PAIRING_TTL_MINUTES", "15")
                ),
                "assistant_context_visibility": os.getenv(
                    "ASSISTANT_CONTEXT_VISIBILITY", "allowlist"
                ),
                "assistant_group_trigger_policy": os.getenv(
                    "ASSISTANT_GROUP_TRIGGER_POLICY", "mention"
                ),
                "assistant_default_mode": os.getenv("ASSISTANT_DEFAULT_MODE", "secretary"),
                "tg_mini_app_url": os.getenv("TG_MINI_APP_URL", ""),
                "bot_enabled_features": _parse_feature_names(
                    os.getenv("BOT_ENABLED_FEATURES", "all")
                ),
                "bot_disabled_features": _parse_feature_names(
                    os.getenv("BOT_DISABLED_FEATURES", "")
                ),
                "live_price_refresh_enabled": (
                    os.getenv("LIVE_PRICE_REFRESH_ENABLED", "false").lower() == "true"
                ),
                "live_price_refresh_limit_per_query": int(
                    os.getenv("LIVE_PRICE_REFRESH_LIMIT_PER_QUERY", "10")
                ),
                "admin_telegram_ids": _parse_admin_telegram_ids(
                    os.getenv("ADMIN_TELEGRAM_IDS", "[]")
                ),
                "magnit_shop_code": os.getenv("MAGNIT_SHOP_CODE") or None,
                "magnit_shop_type": os.getenv("MAGNIT_SHOP_TYPE") or None,
                "pyaterochka_store_id": os.getenv("PYATEROCHKA_STORE_ID") or None,
                "pyaterochka_city_id": os.getenv("PYATEROCHKA_CITY_ID") or None,
                "spar_region": os.getenv("SPAR_REGION") or None,
                "smart_store_id": os.getenv("SMART_STORE_ID") or None,
                "fix_price_city": os.getenv("FIX_PRICE_CITY") or None,
            }
            env_data.update(data)
            super().__init__(**env_data)  # type: ignore[arg-type]
            return
        super().__init__(**data)  # type: ignore[arg-type]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _parse_admin_telegram_ids(value: str) -> list[int]:
    text = value.strip()
    if not text:
        return []
    if text.startswith("["):
        raw_ids = json.loads(text)
    else:
        raw_ids = [part.strip() for part in text.split(",") if part.strip()]
    if not isinstance(raw_ids, list):
        raise ValueError("ADMIN_TELEGRAM_IDS must be a JSON list or comma-separated IDs")
    return [int(item) for item in raw_ids]


def _parse_feature_names(value: str) -> list[str]:
    text = value.strip()
    if not text:
        return []
    if text.startswith("["):
        raw_names = json.loads(text)
    else:
        raw_names = [part.strip() for part in text.split(",") if part.strip()]
    if not isinstance(raw_names, list):
        raise ValueError("Feature flags must be a JSON list or comma-separated names")
    return [str(item).strip() for item in raw_names if str(item).strip()]
