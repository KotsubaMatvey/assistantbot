from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.services.market_watch import (
    MarketQuote,
    MarketWatchResult,
    analyze_market_watch,
    format_market_brief,
)


def test_analyze_market_watch_builds_sentiment_and_signals() -> None:
    brief = analyze_market_watch(
        MarketWatchResult(
            quotes=[
                MarketQuote(
                    key="btc",
                    name="Bitcoin",
                    value=Decimal("72000"),
                    unit=" USD",
                    source="Yahoo Finance",
                    change=Decimal("2000"),
                    change_percent=Decimal("2.86"),
                ),
                MarketQuote(
                    key="spx",
                    name="S&P 500",
                    value=Decimal("5100"),
                    unit=" pt",
                    source="Yahoo Finance",
                    change=Decimal("60"),
                    change_percent=Decimal("1.19"),
                ),
                MarketQuote(
                    key="nasdaq",
                    name="Nasdaq Composite",
                    value=Decimal("16500"),
                    unit=" pt",
                    source="Yahoo Finance",
                    change=Decimal("240"),
                    change_percent=Decimal("1.48"),
                ),
                MarketQuote(
                    key="dow",
                    name="Dow Jones",
                    value=Decimal("39000"),
                    unit=" pt",
                    source="Yahoo Finance",
                    change=Decimal("200"),
                    change_percent=Decimal("0.52"),
                ),
                MarketQuote(
                    key="btc.d",
                    name="BTC Dominance",
                    value=Decimal("49.8"),
                    unit="%",
                    source="CoinGecko",
                ),
            ],
            fetched_at=datetime(2026, 5, 7, 6, 0, tzinfo=UTC),
        )
    )

    assert brief.sentiment_label == "positive"
    assert brief.risk_regime == "risk-on"
    assert brief.signals[0].status == "strengthened"
    assert brief.signals[1].status == "strengthened"
    assert brief.signals[2].status == "weakened"


def test_format_market_brief_keeps_data_gaps_visible() -> None:
    text = format_market_brief(
        MarketWatchResult(
            quotes=[
                MarketQuote(
                    key="btc",
                    name="Bitcoin",
                    value=None,
                    unit=" USD",
                    source="Yahoo Finance",
                    error="timeout",
                )
            ],
            fetched_at=datetime(2026, 5, 7, 6, 0, tzinfo=UTC),
        )
    )

    assert "Market brief" in text
    assert "Data gaps: Bitcoin" in text
    assert "not investment advice" in text
