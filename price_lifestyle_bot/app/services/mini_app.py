from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

MAX_RAW_PAYLOAD_BYTES = 8_192
MAX_BASKET_TEXT_CHARS = 2_000
MAX_ASSISTANT_TEXT_CHARS = 500

ALLOWED_COMMANDS = {
    "markets",
    "market_brief",
    "status",
    "capability_center",
    "agenda",
    "lifestyle_context",
    "compact",
    "new",
    "morning",
    "evening",
    "week",
    "price_alerts",
    "check_alerts",
    "pantry",
    "pantry_plan",
    "pantry_deals",
    "budget",
    "budget_plan",
    "expense",
    "income",
    "accounts",
    "subscriptions",
    "cashflow",
    "assistants",
    "today",
    "tasks",
    "people",
    "objects",
    "recent",
    "sources",
    "source_list",
    "source_sync",
    "memory_tree",
    "memory_profile",
    "weekly_summary",
    "tools",
    "skills",
    "assistant_capabilities",
}


@dataclass(frozen=True)
class MiniAppManifest:
    enabled: bool
    url: str
    features: list[str]


@dataclass(frozen=True)
class MiniAppPayload:
    type: str
    command: str = ""
    text: str = ""


def mini_app_manifest(url: str) -> MiniAppManifest:
    clean_url = url.strip()
    return MiniAppManifest(
        enabled=bool(clean_url),
        url=clean_url,
        features=[
            "shopping",
            "memory_search",
            "tasks",
            "agenda",
            "market_watch",
            "market_brief",
            "price_alerts",
            "check_alerts",
            "pantry",
            "pantry_plan",
            "pantry_deals",
            "budget",
            "budget_plan",
            "finance",
            "accounts",
            "subscriptions",
            "cashflow",
            "family",
            "people",
            "objects",
            "daily_command_center",
            "evening_review",
            "week_plan",
            "jobs",
            "skills",
            "safe_assistants",
            "pixel_assistant",
            "assistant_status",
            "capability_center",
            "memory_tree",
            "connected_sources",
            "tool_registry",
            "lifestyle_context",
            "admin_doctor",
            "live_mini_app_api",
            "mini_app_finance_forms",
            "mini_app_task_capture",
        ],
    )


def format_mini_app_status(manifest: MiniAppManifest) -> str:
    if not manifest.enabled:
        return (
            "Mini App готов, но URL не настроен.\n"
            "Telegram Mini App требует публичный HTTPS-адрес.\n"
            "1. Опубликуй папку miniapp/ как static site.\n"
            "2. Укажи в .env: TG_MINI_APP_URL=https://your-domain.example/\n"
            "3. Перезапусти бота и снова отправь /mini_app."
        )
    return "Mini App URL:\n" + manifest.url + "\nFeatures:\n" + "\n".join(
        f"- {feature}" for feature in manifest.features
    )


def parse_mini_app_payload(raw_data: str) -> MiniAppPayload:
    if len(raw_data.encode("utf-8")) > MAX_RAW_PAYLOAD_BYTES:
        raise ValueError("Mini App payload is too large")
    try:
        raw: Any = json.loads(raw_data)
    except json.JSONDecodeError as exc:
        raise ValueError("Mini App payload must be JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("Mini App payload must be an object")
    payload_type = str(raw.get("type", "")).strip()
    if payload_type == "command":
        command = str(raw.get("command", "")).strip().lower()
        if command not in ALLOWED_COMMANDS:
            raise ValueError("unsupported Mini App command")
        return MiniAppPayload(type=payload_type, command=command)
    if payload_type == "basket_compare":
        text = str(raw.get("text", "")).strip()
        if not text:
            raise ValueError("basket text is empty")
        if len(text) > MAX_BASKET_TEXT_CHARS:
            raise ValueError("basket text is too large")
        return MiniAppPayload(type=payload_type, text=text)
    if payload_type == "assistant_message":
        text = str(raw.get("text", "")).strip()
        if not text:
            raise ValueError("assistant message is empty")
        if len(text) > MAX_ASSISTANT_TEXT_CHARS:
            raise ValueError("assistant message is too large")
        return MiniAppPayload(type=payload_type, text=text)
    raise ValueError("unsupported Mini App payload type")
