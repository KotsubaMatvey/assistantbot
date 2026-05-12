from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from app.db.models import PriceSource, ScrapeRunStatus
from app.db.repositories.prices import add_price_snapshot
from app.db.repositories.products import upsert_store_product
from app.db.repositories.stores import create_scrape_run, finish_scrape_run, get_store_by_slug
from app.logging_config import get_logger
from app.scrapers.registry import get_scraper
from app.scrapers.types import ScrapedProduct
from app.scripts.scrape_once import classify_scrape_run_result
from app.services.basket_parser import BasketItemParsed
from app.services.product_normalizer import build_normalized_key, calculate_unit_price

logger = get_logger(__name__)


@dataclass(frozen=True)
class StoreRefreshResult:
    store_slug: str
    products_found: int
    prices_saved: int
    error_message: str | None = None
    status: ScrapeRunStatus = ScrapeRunStatus.success

    @property
    def failed(self) -> bool:
        return self.status == ScrapeRunStatus.failed or (
            self.status == ScrapeRunStatus.success and self.error_message is not None
        )

    @property
    def degraded(self) -> bool:
        return self.failed or self.status == ScrapeRunStatus.partial


@dataclass(frozen=True)
class LivePriceRefreshResult:
    stores: list[StoreRefreshResult]

    @property
    def failed_store_slugs(self) -> list[str]:
        return [store.store_slug for store in self.stores if store.failed]

    @property
    def degraded_store_slugs(self) -> list[str]:
        return [store.store_slug for store in self.stores if store.degraded]


def build_live_price_queries(items: list[BasketItemParsed]) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    for item in items:
        query = str(item.attributes.get("search_text", "")).strip()
        if not query:
            query = item.raw_text.strip() or item.name.strip()
        normalized = query.lower()
        if query and normalized not in seen:
            queries.append(query)
            seen.add(normalized)
    return queries


async def refresh_prices_for_items(
    items: list[BasketItemParsed],
    store_slugs: list[str],
) -> LivePriceRefreshResult:
    queries = build_live_price_queries(items)
    unique_slugs = list(dict.fromkeys(store_slugs))
    if not queries or not unique_slugs:
        return LivePriceRefreshResult(stores=[])

    results = await asyncio.gather(
        *(refresh_store_prices_for_queries(slug, queries) for slug in unique_slugs)
    )
    return LivePriceRefreshResult(stores=list(results))


async def refresh_store_prices_for_queries(
    store_slug: str,
    queries: list[str],
    *,
    limit_per_query: int = 10,
) -> StoreRefreshResult:
    from app.db.session import SessionLocal

    async with SessionLocal() as session:
        store = await get_store_by_slug(session, store_slug)
        if store is None:
            return StoreRefreshResult(
                store_slug=store_slug,
                products_found=0,
                prices_saved=0,
                error_message="store is not seeded",
                status=ScrapeRunStatus.failed,
            )

        run = await create_scrape_run(session, store.id)
        await session.commit()
        status = ScrapeRunStatus.success
        error_message: str | None = None
        products_found = 0
        prices_saved = 0
        try:
            products = await _search_store_products(
                store_slug,
                queries,
                limit_per_query=limit_per_query,
            )
            products_found = len(products)
            for product in products:
                unit_price = product.unit_price
                unit_price_unit = product.unit_price_unit
                if unit_price is None:
                    unit_price, unit_price_unit = calculate_unit_price(
                        product.final_price,
                        product.quantity_value,
                        product.quantity_unit,
                    )
                store_product = await upsert_store_product(
                    session,
                    store_id=store.id,
                    external_id=product.external_id,
                    source_url=product.source_url,
                    raw_title=product.title,
                    normalized_title=build_normalized_key(product.title),
                    brand=product.brand,
                    category=product.category,
                    quantity_value=product.quantity_value,
                    quantity_unit=product.quantity_unit,
                )
                await add_price_snapshot(
                    session,
                    store_product_id=store_product.id,
                    regular_price=product.regular_price,
                    old_price=product.old_price,
                    promo_price=product.promo_price,
                    card_price=product.card_price,
                    final_price=product.final_price,
                    price_type=product.price_type,
                    unit_price=unit_price,
                    unit_price_unit=unit_price_unit,
                    in_stock=product.in_stock,
                    source=PriceSource.html,
                    scraped_at=datetime.now(UTC),
                )
                prices_saved += 1
        except Exception as exc:
            status = ScrapeRunStatus.failed
            error_message = str(exc)
            logger.exception(
                "live_price_refresh_failed",
                store_slug=store_slug,
                error=error_message,
            )
        if status != ScrapeRunStatus.failed:
            status, error_message = classify_scrape_run_result(products_found, prices_saved)
            if status == ScrapeRunStatus.partial:
                logger.warning(
                    "live_price_refresh_partial",
                    store_slug=store_slug,
                    products=products_found,
                    prices=prices_saved,
                    reason=error_message,
                )

        await finish_scrape_run(
            session,
            run,
            status=status,
            products_found=products_found,
            prices_found=prices_saved,
            error_message=error_message,
        )
        await session.commit()
        return StoreRefreshResult(
            store_slug=store_slug,
            products_found=products_found,
            prices_saved=prices_saved,
            error_message=error_message,
            status=status,
        )


async def _search_store_products(
    store_slug: str,
    queries: list[str],
    *,
    limit_per_query: int,
) -> list[ScrapedProduct]:
    scraper = get_scraper(store_slug)
    products: list[ScrapedProduct] = []
    seen: set[tuple[str | None, str | None, str]] = set()
    try:
        for query in queries:
            for product in (await scraper.search_products(query))[:limit_per_query]:
                key = (product.external_id, product.source_url, product.title)
                if key in seen:
                    continue
                seen.add(key)
                products.append(product)
    finally:
        await scraper.close()
    return products
