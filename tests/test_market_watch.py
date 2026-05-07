from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.services.market_watch import (
    MarketAsset,
    MarketQuote,
    MarketWatchResult,
    format_market_watch,
    parse_yahoo_quote,
)


def test_parse_yahoo_quote_calculates_change_percent() -> None:
    quote = parse_yahoo_quote(
        asset=MarketAsset("spx", "S&P 500", "^GSPC"),
        payload={
            "chart": {
                "result": [
                    {
                        "meta": {
                            "regularMarketPrice": 5100,
                            "previousClose": 5000,
                        }
                    }
                ]
            }
        },
    )

    assert quote.value == Decimal("5100")
    assert quote.change == Decimal("100")
    assert quote.change_percent == Decimal("2.00")


def test_format_market_watch_keeps_failed_quotes_visible() -> None:
    text = format_market_watch(
        MarketWatchResult(
            quotes=[
                MarketQuote(
                    key="btc",
                    name="Bitcoin",
                    value=Decimal("70000"),
                    unit=" USD",
                    source="Yahoo Finance",
                    change=Decimal("1000"),
                    change_percent=Decimal("1.45"),
                ),
                MarketQuote(
                    key="btc.d",
                    name="BTC Dominance",
                    value=None,
                    unit="%",
                    source="CoinGecko",
                    error="timeout",
                ),
            ],
            fetched_at=datetime(2026, 5, 7, 6, 0, tzinfo=UTC),
        )
    )

    assert "Bitcoin: 70000.00 USD (+1000.00, +1.45%)" in text
    assert "BTC Dominance: нет данных (timeout)" in text
