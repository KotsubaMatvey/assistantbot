from __future__ import annotations

from app.db.models import ScrapeRunStatus
from app.scripts.refresh_prices import RefreshAllPricesResult, StoreRefreshSummary
from app.scripts.scrape_once import ScrapeStoreResult, classify_scrape_run_result


def test_classify_scrape_run_result_marks_failures_and_partials() -> None:
    assert classify_scrape_run_result(3, 3) == (ScrapeRunStatus.success, None)
    assert classify_scrape_run_result(0, 0) == (
        ScrapeRunStatus.partial,
        "scraper returned no products",
    )
    assert classify_scrape_run_result(3, 0) == (
        ScrapeRunStatus.partial,
        "no prices saved for scraped products",
    )
    assert classify_scrape_run_result(3, 2) == (
        ScrapeRunStatus.partial,
        "saved prices for 2/3 scraped products",
    )
    assert classify_scrape_run_result(0, 0, "timeout") == (
        ScrapeRunStatus.failed,
        "timeout",
    )


def test_scrape_store_result_stays_tuple_unpack_compatible() -> None:
    result = ScrapeStoreResult(
        store_slug="smart",
        status=ScrapeRunStatus.partial,
        products_found=2,
        prices_found=1,
        error_message="saved prices for 1/2 scraped products",
    )

    products, prices = result

    assert (products, prices) == (2, 1)
    assert result.degraded is True


def test_refresh_all_prices_result_summarizes_degraded_stores() -> None:
    result = RefreshAllPricesResult(
        stores=[
            StoreRefreshSummary("smart", ScrapeRunStatus.success, 3, 3),
            StoreRefreshSummary(
                "spar",
                ScrapeRunStatus.partial,
                0,
                0,
                "scraper returned no products",
            ),
            StoreRefreshSummary("magnit", ScrapeRunStatus.failed, 0, 0, "timeout"),
        ]
    )

    assert result.total_products_found == 3
    assert result.total_prices_found == 3
    assert result.partial_store_slugs == ["spar"]
    assert result.failed_store_slugs == ["magnit"]
    assert result.degraded_store_slugs == ["spar", "magnit"]
