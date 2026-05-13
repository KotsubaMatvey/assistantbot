from __future__ import annotations

import asyncio

from app.db.models import ScrapeRunStatus
from app.services import live_price_refresh
from app.services.basket_parser import parse_basket
from app.services.live_price_refresh import StoreRefreshResult


def test_build_live_price_queries_deduplicates_raw_items() -> None:
    items = parse_basket("2x молоко 1 л\nМолоко 1 л\nсахар 1 кг")

    assert live_price_refresh.build_live_price_queries(items) == ["молоко 1 л", "сахар 1 кг"]


def test_refresh_prices_for_items_calls_selected_stores(monkeypatch) -> None:
    calls: list[tuple[str, list[str], int]] = []

    async def fake_refresh(
        store_slug: str,
        queries: list[str],
        *,
        limit_per_query: int = 10,
    ) -> StoreRefreshResult:
        calls.append((store_slug, queries, limit_per_query))
        return StoreRefreshResult(store_slug=store_slug, products_found=1, prices_saved=1)

    monkeypatch.setattr(live_price_refresh, "refresh_store_prices_for_queries", fake_refresh)

    result = asyncio.run(
        live_price_refresh.refresh_prices_for_items(
            parse_basket("молоко 1 л\nсахар 1 кг"),
            ["smart", "smart", "magnit"],
            limit_per_query=3,
        )
    )

    assert calls == [
        ("smart", ["молоко 1 л", "сахар 1 кг"], 3),
        ("magnit", ["молоко 1 л", "сахар 1 кг"], 3),
    ]
    assert result.failed_store_slugs == []


def test_failed_store_slugs_returns_only_failed_refreshes() -> None:
    result = live_price_refresh.LivePriceRefreshResult(
        stores=[
            StoreRefreshResult("smart", products_found=1, prices_saved=1),
            StoreRefreshResult(
                "spar",
                products_found=0,
                prices_saved=0,
                error_message="scraper returned no products",
                status=ScrapeRunStatus.partial,
            ),
            StoreRefreshResult(
                "magnit",
                products_found=0,
                prices_saved=0,
                error_message="timeout",
                status=ScrapeRunStatus.failed,
            ),
        ]
    )

    assert result.failed_store_slugs == ["magnit"]
    assert result.degraded_store_slugs == ["spar", "magnit"]
