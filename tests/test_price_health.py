from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.price_health import (
    CatalogHealth,
    StorePriceHealth,
    format_catalog_health,
    human_age,
)


def test_human_age_formats_missing_and_recent_values() -> None:
    now = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
    assert human_age(None, now=now) == "нет данных"
    assert human_age(now - timedelta(minutes=5), now=now) == "5 мин назад"
    assert human_age(now - timedelta(hours=3), now=now) == "3 ч назад"
    assert human_age(now - timedelta(days=2), now=now) == "2 д назад"


def test_catalog_health_counts_store_states() -> None:
    fresh = StorePriceHealth(
        slug="smart",
        display_name="Smart",
        parser_status="partial",
        products_count=10,
        priced_products_count=8,
        snapshots_count=20,
        latest_price_at=datetime.now(UTC),
        last_scrape_finished_at=datetime.now(UTC),
        last_scrape_status="success",
        last_scrape_error=None,
        freshness_hours=24,
    )
    empty = StorePriceHealth(
        slug="spar",
        display_name="SPAR",
        parser_status="partial",
        products_count=0,
        priced_products_count=0,
        snapshots_count=0,
        latest_price_at=None,
        last_scrape_finished_at=None,
        last_scrape_status=None,
        last_scrape_error=None,
        freshness_hours=24,
    )
    failed = StorePriceHealth(
        slug="magnit",
        display_name="Магнит",
        parser_status="active",
        products_count=10,
        priced_products_count=10,
        snapshots_count=20,
        latest_price_at=datetime.now(UTC),
        last_scrape_finished_at=datetime.now(UTC),
        last_scrape_status="failed",
        last_scrape_error="timeout",
        freshness_hours=24,
    )
    partial = StorePriceHealth(
        slug="pyaterochka",
        display_name="Пятерочка",
        parser_status="active",
        products_count=10,
        priced_products_count=5,
        snapshots_count=10,
        latest_price_at=datetime.now(UTC),
        last_scrape_finished_at=datetime.now(UTC),
        last_scrape_status="partial",
        last_scrape_error="saved prices for 5/10 scraped products",
        freshness_hours=24,
    )
    health = CatalogHealth(stores=[fresh, empty, failed, partial], freshness_hours=24)
    assert health.fresh_store_count == 1
    assert health.empty_store_count == 1
    assert health.failed_store_count == 1
    assert health.partial_store_count == 1
    assert health.degraded_store_count == 3
    assert failed.status_label == "ошибка scraping"
    assert partial.status_label == "частично"


def test_format_catalog_health_includes_degraded_scraper_summary() -> None:
    store = StorePriceHealth(
        slug="smart",
        display_name="Smart",
        parser_status="partial",
        products_count=0,
        priced_products_count=0,
        snapshots_count=0,
        latest_price_at=None,
        last_scrape_finished_at=datetime.now(UTC),
        last_scrape_status="partial",
        last_scrape_error="scraper returned no products",
        freshness_hours=24,
    )

    text = format_catalog_health(CatalogHealth(stores=[store], freshness_hours=24))

    assert "Scraper: degraded 1, partial 1, failed 0" in text
    assert "/admin_scraper_diag smart молоко" in text
