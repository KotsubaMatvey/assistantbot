from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


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
            "price_alerts",
            "pantry",
            "budget",
            "family",
            "jobs",
            "skills",
            "safe_assistants",
            "pixel_assistant",
            "assistant_status",
            "admin_doctor",
        ],
    )


def format_mini_app_status(manifest: MiniAppManifest) -> str:
    if not manifest.enabled:
        return "Mini App foundation is ready, but TG_MINI_APP_URL is not set."
    return "Mini App URL:\n" + manifest.url + "\nFeatures:\n" + "\n".join(
        f"- {feature}" for feature in manifest.features
    )


def parse_mini_app_payload(raw_data: str) -> MiniAppPayload:
    try:
        raw: Any = json.loads(raw_data)
    except json.JSONDecodeError as exc:
        raise ValueError("Mini App payload must be JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("Mini App payload must be an object")
    payload_type = str(raw.get("type", "")).strip()
    if payload_type == "command":
        command = str(raw.get("command", "")).strip().lower()
        if command not in {
            "markets",
            "status",
            "agenda",
            "compact",
            "new",
            "morning",
            "price_alerts",
            "pantry",
            "budget",
            "assistants",
        }:
            raise ValueError("unsupported Mini App command")
        return MiniAppPayload(type=payload_type, command=command)
    if payload_type == "basket_compare":
        text = str(raw.get("text", "")).strip()
        if not text:
            raise ValueError("basket text is empty")
        return MiniAppPayload(type=payload_type, text=text)
    if payload_type == "assistant_message":
        text = str(raw.get("text", "")).strip()
        if not text:
            raise ValueError("assistant message is empty")
        return MiniAppPayload(type=payload_type, text=text)
    raise ValueError("unsupported Mini App payload type")
