from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from app.db.models import ScrapeRunStatus
from app.db.repositories.stores import list_enabled_stores
from app.db.session import SessionLocal, dispose_engine
from app.logging_config import configure_logging, get_logger
from app.scripts.scrape_once import ScrapeStoreResult, classify_scrape_run_result, scrape_store

logger = get_logger(__name__)


@dataclass(frozen=True)
class StoreRefreshSummary:
    store_slug: str
    status: ScrapeRunStatus
    products_found: int
    prices_found: int
    error_message: str | None = None

    @property
    def degraded(self) -> bool:
        return self.status in {ScrapeRunStatus.partial, ScrapeRunStatus.failed}


@dataclass(frozen=True)
class RefreshAllPricesResult:
    stores: list[StoreRefreshSummary]

    @property
    def total_products_found(self) -> int:
        return sum(store.products_found for store in self.stores)

    @property
    def total_prices_found(self) -> int:
        return sum(store.prices_found for store in self.stores)

    @property
    def failed_store_slugs(self) -> list[str]:
        return [
            store.store_slug for store in self.stores if store.status == ScrapeRunStatus.failed
        ]

    @property
    def partial_store_slugs(self) -> list[str]:
        return [
            store.store_slug for store in self.stores if store.status == ScrapeRunStatus.partial
        ]

    @property
    def degraded_store_slugs(self) -> list[str]:
        return [store.store_slug for store in self.stores if store.degraded]


def _summary_from_scrape_result(result: ScrapeStoreResult | tuple[int, int]) -> StoreRefreshSummary:
    if isinstance(result, ScrapeStoreResult):
        return StoreRefreshSummary(
            store_slug=result.store_slug,
            status=result.status,
            products_found=result.products_found,
            prices_found=result.prices_found,
            error_message=result.error_message,
        )
    products_found, prices_found = result
    status, error_message = classify_scrape_run_result(products_found, prices_found)
    return StoreRefreshSummary(
        store_slug="unknown",
        status=status,
        products_found=products_found,
        prices_found=prices_found,
        error_message=error_message,
    )


async def refresh_all_prices() -> RefreshAllPricesResult:
    async with SessionLocal() as session:
        stores = await list_enabled_stores(session)
    summaries: list[StoreRefreshSummary] = []
    for store in stores:
        try:
            summary = _summary_from_scrape_result(await scrape_store(store.slug))
            if summary.store_slug == "unknown":
                summary = StoreRefreshSummary(
                    store_slug=store.slug,
                    status=summary.status,
                    products_found=summary.products_found,
                    prices_found=summary.prices_found,
                    error_message=summary.error_message,
                )
        except Exception as exc:
            summary = StoreRefreshSummary(
                store_slug=store.slug,
                status=ScrapeRunStatus.failed,
                products_found=0,
                prices_found=0,
                error_message=str(exc),
            )
            logger.exception("refresh_store_failed", store_slug=store.slug, error=str(exc))
        summaries.append(summary)
        log_kwargs = {
            "store_slug": summary.store_slug,
            "status": summary.status.value,
            "products": summary.products_found,
            "prices": summary.prices_found,
            "error": summary.error_message,
        }
        if summary.degraded:
            logger.warning("refresh_store_degraded", **log_kwargs)
        else:
            logger.info("refresh_store_finished", **log_kwargs)
    return RefreshAllPricesResult(stores=summaries)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if not args.all:
        raise SystemExit("use --all")
    configure_logging()
    result = await refresh_all_prices()
    logger.info(
        "refresh_all_prices_finished",
        stores=len(result.stores),
        degraded=result.degraded_store_slugs,
        products=result.total_products_found,
        prices=result.total_prices_found,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        asyncio.run(dispose_engine())
