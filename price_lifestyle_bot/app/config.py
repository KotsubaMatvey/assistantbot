from __future__ import annotations

import json
import os
from functools import lru_cache

from pydantic import Field
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseModel as BaseSettings

    def SettingsConfigDict(**kwargs: object) -> dict[str, object]:
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
    admin_telegram_ids: list[int] = Field(default_factory=list)

    magnit_shop_code: str | None = None
    magnit_shop_type: str | None = None
    pyaterochka_store_id: str | None = None
    pyaterochka_city_id: str | None = None
    spar_region: str | None = None
    smart_store_id: str | None = None
    fix_price_city: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **data: object) -> None:
        if BaseSettings.__module__.startswith("pydantic."):
            if load_dotenv is not None:
                load_dotenv()
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
                "admin_telegram_ids": json.loads(os.getenv("ADMIN_TELEGRAM_IDS", "[]")),
                "magnit_shop_code": os.getenv("MAGNIT_SHOP_CODE") or None,
                "magnit_shop_type": os.getenv("MAGNIT_SHOP_TYPE") or None,
                "pyaterochka_store_id": os.getenv("PYATEROCHKA_STORE_ID") or None,
                "pyaterochka_city_id": os.getenv("PYATEROCHKA_CITY_ID") or None,
                "spar_region": os.getenv("SPAR_REGION") or None,
                "smart_store_id": os.getenv("SMART_STORE_ID") or None,
                "fix_price_city": os.getenv("FIX_PRICE_CITY") or None,
            }
            env_data.update(data)
            super().__init__(**env_data)
            return
        super().__init__(**data)


@lru_cache
def get_settings() -> Settings:
    return Settings()
