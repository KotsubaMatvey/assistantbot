from __future__ import annotations

import argparse
import asyncio

from app.db.repositories.stores import list_enabled_stores
from app.db.session import SessionLocal, dispose_engine
from app.logging_config import configure_logging, get_logger
from app.scripts.scrape_once import scrape_store

logger = get_logger(__name__)


async def refresh_all_prices() -> None:
    async with SessionLocal() as session:
        stores = await list_enabled_stores(session)
    for store in stores:
        try:
            products, prices = await scrape_store(store.slug)
            logger.info(
                "refresh_store_finished",
                store_slug=store.slug,
                products=products,
                prices=prices,
            )
        except Exception as exc:
            logger.exception("refresh_store_failed", store_slug=store.slug, error=str(exc))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if not args.all:
        raise SystemExit("use --all")
    configure_logging()
    await refresh_all_prices()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        asyncio.run(dispose_engine())

