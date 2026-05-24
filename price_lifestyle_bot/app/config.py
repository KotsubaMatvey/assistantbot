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
    llm_enabled: bool = False
    llm_cloud_context_allowed: bool = False
    llm_context_mode: str = "snippets"
    llm_timeout_seconds: float = 30.0
    llm_max_context_notes: int = 5
    llm_max_output_tokens: int = 700
    llm_temperature: float = 0.2
    llm_daily_limit_cooldown_hours: int = 24
    llm_provider_order: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "groq",
            "cerebras",
            "openrouter",
            "mistral",
            "github_models",
            "zai",
            "nvidia",
            "llm7",
            "ovh",
            "siliconflow",
        ]
    )
    llm_provider_specs_json: str = ""
    llm_groq_api_key: str = ""
    llm_groq_model: str = "llama-3.1-8b-instant"
    llm_cerebras_api_key: str = ""
    llm_cerebras_model: str = "llama3.1-8b"
    llm_openrouter_api_key: str = ""
    llm_openrouter_model: str = "openrouter/free"
    llm_openrouter_site_url: str = ""
    llm_openrouter_app_name: str = "Assistant Bot"
    llm_mistral_api_key: str = ""
    llm_mistral_model: str = "mistral-small-latest"
    llm_github_models_token: str = ""
    llm_github_models_model: str = "openai/gpt-4.1-mini"
    llm_zai_api_key: str = ""
    llm_zai_model: str = "glm-4.5-flash"
    llm_nvidia_api_key: str = ""
    llm_nvidia_model: str = "nvidia/nemotron-3-nano-30b-a3b"
    llm_llm7_api_key: str = ""
    llm_llm7_model: str = "mistral-small-3.1-24b"
    llm_ovh_api_key: str = ""
    llm_ovh_model: str = "Meta-Llama-3_1-8B-Instruct"
    llm_siliconflow_api_key: str = ""
    llm_siliconflow_model: str = "Qwen/Qwen3-8B"
    tg_mini_app_url: str = ""
    mini_app_api_enabled: bool = True
    mini_app_api_host: str = "0.0.0.0"
    mini_app_api_port: int = 8080
    mini_app_static_dir: str = "miniapp/dist"
    mini_app_dev_auth_enabled: bool = False
    mini_app_init_data_max_age_seconds: int = Field(default=3600, ge=60, le=86400)
    mini_app_rate_limit_per_minute: int = Field(default=120, ge=10, le=10000)
    admin_backup_enabled: bool = False
    admin_backup_interval_hours: int = Field(default=24, ge=1, le=168)
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

    @field_validator("llm_provider_order", mode="before")
    @classmethod
    def parse_llm_provider_order(cls, value: object) -> list[str] | object:
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
                "llm_enabled": os.getenv("LLM_ENABLED", "false").lower() == "true",
                "llm_cloud_context_allowed": (
                    os.getenv("LLM_CLOUD_CONTEXT_ALLOWED", "false").lower() == "true"
                ),
                "llm_context_mode": os.getenv("LLM_CONTEXT_MODE", "snippets"),
                "llm_timeout_seconds": float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
                "llm_max_context_notes": int(os.getenv("LLM_MAX_CONTEXT_NOTES", "5")),
                "llm_max_output_tokens": int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "700")),
                "llm_temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
                "llm_daily_limit_cooldown_hours": int(
                    os.getenv("LLM_DAILY_LIMIT_COOLDOWN_HOURS", "24")
                ),
                "llm_provider_order": _parse_feature_names(
                    os.getenv(
                        "LLM_PROVIDER_ORDER",
                        "groq,cerebras,openrouter,mistral,github_models,zai,nvidia,llm7,ovh,siliconflow",
                    )
                ),
                "llm_provider_specs_json": os.getenv("LLM_PROVIDER_SPECS_JSON", ""),
                "llm_groq_api_key": os.getenv("LLM_GROQ_API_KEY", ""),
                "llm_groq_model": os.getenv("LLM_GROQ_MODEL", "llama-3.1-8b-instant"),
                "llm_cerebras_api_key": os.getenv("LLM_CEREBRAS_API_KEY", ""),
                "llm_cerebras_model": os.getenv("LLM_CEREBRAS_MODEL", "llama3.1-8b"),
                "llm_openrouter_api_key": os.getenv("LLM_OPENROUTER_API_KEY", ""),
                "llm_openrouter_model": os.getenv("LLM_OPENROUTER_MODEL", "openrouter/free"),
                "llm_openrouter_site_url": os.getenv("LLM_OPENROUTER_SITE_URL", ""),
                "llm_openrouter_app_name": os.getenv(
                    "LLM_OPENROUTER_APP_NAME", "Assistant Bot"
                ),
                "llm_mistral_api_key": os.getenv("LLM_MISTRAL_API_KEY", ""),
                "llm_mistral_model": os.getenv("LLM_MISTRAL_MODEL", "mistral-small-latest"),
                "llm_github_models_token": os.getenv("LLM_GITHUB_MODELS_TOKEN", ""),
                "llm_github_models_model": os.getenv(
                    "LLM_GITHUB_MODELS_MODEL", "openai/gpt-4.1-mini"
                ),
                "llm_zai_api_key": os.getenv("LLM_ZAI_API_KEY", ""),
                "llm_zai_model": os.getenv("LLM_ZAI_MODEL", "glm-4.5-flash"),
                "llm_nvidia_api_key": os.getenv("LLM_NVIDIA_API_KEY", ""),
                "llm_nvidia_model": os.getenv(
                    "LLM_NVIDIA_MODEL", "nvidia/nemotron-3-nano-30b-a3b"
                ),
                "llm_llm7_api_key": os.getenv("LLM_LLM7_API_KEY", ""),
                "llm_llm7_model": os.getenv("LLM_LLM7_MODEL", "mistral-small-3.1-24b"),
                "llm_ovh_api_key": os.getenv("LLM_OVH_API_KEY", ""),
                "llm_ovh_model": os.getenv("LLM_OVH_MODEL", "Meta-Llama-3_1-8B-Instruct"),
                "llm_siliconflow_api_key": os.getenv("LLM_SILICONFLOW_API_KEY", ""),
                "llm_siliconflow_model": os.getenv(
                    "LLM_SILICONFLOW_MODEL", "Qwen/Qwen3-8B"
                ),
                "tg_mini_app_url": os.getenv("TG_MINI_APP_URL", ""),
                "mini_app_api_enabled": (
                    os.getenv("MINI_APP_API_ENABLED", "true").lower() == "true"
                ),
                "mini_app_api_host": os.getenv("MINI_APP_API_HOST", "0.0.0.0"),
                "mini_app_api_port": int(os.getenv("MINI_APP_API_PORT", "8080")),
                "mini_app_static_dir": os.getenv("MINI_APP_STATIC_DIR", "miniapp/dist"),
                "mini_app_dev_auth_enabled": (
                    os.getenv("MINI_APP_DEV_AUTH_ENABLED", "false").lower() == "true"
                ),
                "mini_app_init_data_max_age_seconds": int(
                    os.getenv("MINI_APP_INIT_DATA_MAX_AGE_SECONDS", "3600")
                ),
                "mini_app_rate_limit_per_minute": int(
                    os.getenv("MINI_APP_RATE_LIMIT_PER_MINUTE", "120")
                ),
                "admin_backup_enabled": os.getenv("ADMIN_BACKUP_ENABLED", "false").lower()
                == "true",
                "admin_backup_interval_hours": int(
                    os.getenv("ADMIN_BACKUP_INTERVAL_HOURS", "24")
                ),
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
