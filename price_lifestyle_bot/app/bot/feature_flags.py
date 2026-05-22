from __future__ import annotations

from collections.abc import Iterable

from app.config import Settings, get_settings

FEATURE_NAMES: tuple[str, ...] = (
    "onboarding",
    "settings",
    "memory",
    "lifestyle",
    "markets",
    "miniapp",
    "shopping",
    "admin",
)


def enabled_feature_names(settings: Settings | None = None) -> tuple[str, ...]:
    runtime_settings = settings or get_settings()
    requested = _normalize_feature_names(runtime_settings.bot_enabled_features)
    disabled = _normalize_feature_names(runtime_settings.bot_disabled_features)
    known = set(FEATURE_NAMES)
    unknown = (requested | disabled) - known - {"all", "*"}
    if unknown:
        unknown_names = ", ".join(sorted(unknown))
        raise ValueError(f"Unknown bot feature flag: {unknown_names}")

    enabled_all = not requested or "all" in requested or "*" in requested
    enabled_names: list[str] = []
    for feature_name in FEATURE_NAMES:
        if feature_name in disabled:
            continue
        if enabled_all or feature_name in requested:
            enabled_names.append(feature_name)
    return tuple(enabled_names)


def is_feature_enabled(feature_name: str, settings: Settings | None = None) -> bool:
    return feature_name in enabled_feature_names(settings)


def _normalize_feature_names(names: Iterable[str]) -> set[str]:
    return {name.strip().lower() for name in names if name.strip()}
