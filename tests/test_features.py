from __future__ import annotations

import pytest
from app.bot.feature_flags import enabled_feature_names
from app.config import Settings


def test_enabled_feature_names_can_allowlist_features() -> None:
    settings = Settings(bot_enabled_features=["shopping", "miniapp"])

    assert enabled_feature_names(settings) == ("miniapp", "shopping")


def test_enabled_feature_names_can_disable_specific_features() -> None:
    settings = Settings(bot_enabled_features=["all"], bot_disabled_features=["miniapp"])

    assert "miniapp" not in enabled_feature_names(settings)


def test_enabled_feature_names_rejects_unknown_flags() -> None:
    settings = Settings(bot_enabled_features=["shopping", "unknown"])

    with pytest.raises(ValueError, match="Unknown bot feature flag: unknown"):
        enabled_feature_names(settings)
