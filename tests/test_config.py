from __future__ import annotations

import pytest
from app.config import Settings


def test_admin_telegram_ids_accept_json_list(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "[123, 456]")

    settings = Settings()

    assert settings.admin_telegram_ids == [123, 456]


def test_admin_telegram_ids_accept_comma_separated_list(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "123, 456")

    settings = Settings()

    assert settings.admin_telegram_ids == [123, 456]


def test_admin_telegram_ids_reject_invalid_values(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "123, nope")

    with pytest.raises(ValueError):
        Settings()


def test_assistant_security_settings_read_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ASSISTANT_ACCESS_MODE", "pairing")
    monkeypatch.setenv("ASSISTANT_APPROVAL_TTL_MINUTES", "10")
    monkeypatch.setenv("ASSISTANT_PAIRING_TTL_MINUTES", "20")
    monkeypatch.setenv("ASSISTANT_CONTEXT_VISIBILITY", "allowlist")
    monkeypatch.setenv("ASSISTANT_GROUP_TRIGGER_POLICY", "mention")
    monkeypatch.setenv("ASSISTANT_DEFAULT_MODE", "buyer")
    monkeypatch.setenv("TG_MINI_APP_URL", "https://example.com/miniapp")

    settings = Settings()

    assert settings.assistant_access_mode == "pairing"
    assert settings.assistant_approval_ttl_minutes == 10
    assert settings.assistant_pairing_ttl_minutes == 20
    assert settings.assistant_context_visibility == "allowlist"
    assert settings.assistant_group_trigger_policy == "mention"
    assert settings.assistant_default_mode == "buyer"
    assert settings.tg_mini_app_url == "https://example.com/miniapp"


def test_feature_flags_and_live_refresh_settings_read_from_env(monkeypatch) -> None:
    monkeypatch.setenv("BOT_ENABLED_FEATURES", "onboarding,shopping")
    monkeypatch.setenv("BOT_DISABLED_FEATURES", '["miniapp"]')
    monkeypatch.setenv("LIVE_PRICE_REFRESH_ENABLED", "false")
    monkeypatch.setenv("LIVE_PRICE_REFRESH_LIMIT_PER_QUERY", "3")

    settings = Settings()

    assert settings.bot_enabled_features == ["onboarding", "shopping"]
    assert settings.bot_disabled_features == ["miniapp"]
    assert settings.live_price_refresh_enabled is False
    assert settings.live_price_refresh_limit_per_query == 3


def test_live_refresh_is_disabled_by_default() -> None:
    settings = Settings()

    assert settings.live_price_refresh_enabled is False
