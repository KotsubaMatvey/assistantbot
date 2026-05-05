from __future__ import annotations

from typing import Any


def user_has_store_card(settings: Any, store_slug: str) -> bool | None:
    attr = f"has_{store_slug}_card"
    if hasattr(settings, attr):
        return bool(getattr(settings, attr))
    return None

