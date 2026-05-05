from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from app.db.models import PriceSource, ScrapeRunStatus
from app.db.repositories.prices import add_price_snapshot
from app.db.repositories.products import upsert_store_product
from app.db.repositories.stores import (
    create_scrape_run,
    finish_scrape_run,
    get_store_by_slug,
)
from app.db.session import SessionLocal, dispose_engine
from app.logging_config import configure_logging, get_logger
from app.scrapers.registry import run_scraper
from app.services.product_normalizer import build_normalized_key

logger = get_logger(__name__)


async def scrape_store(store_slug: str, limit: int | None = None) -> tuple[int, int]:
    async with SessionLocal() as session:
        store = await get_store_by_slug(session, store_slug)
        if store is None:
            raise RuntimeError(f"store is not seeded: {store_slug}")
        run = await create_scrape_run(session, store.id)
        await session.commit()
        products_found = 0
        prices_found = 0
        status = ScrapeRunStatus.success
        error_message: str | None = None
        try:
            scraped_products = await run_scraper(store_slug, limit=limit)
            products_found = len(scraped_products)
            for product in scraped_products:
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
                    unit_price=product.unit_price,
                    unit_price_unit=product.unit_price_unit,
                    in_stock=product.in_stock,
                    source=PriceSource.html,
                    scraped_at=datetime.now(UTC),
                )
                prices_found += 1
        except Exception as exc:
            status = ScrapeRunStatus.failed
            error_message = str(exc)
            logger.exception("scrape_store_failed", store_slug=store_slug, error=error_message)
        await finish_scrape_run(
            session,
            run,
            status=status,
            products_found=products_found,
            prices_found=prices_found,
            error_message=error_message,
        )
        await session.commit()
        return products_found, prices_found


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    configure_logging()
    products, prices = await scrape_store(args.store, args.limit)
    logger.info("scrape_once_finished", store_slug=args.store, products=products, prices=prices)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        asyncio.run(dispose_engine())

