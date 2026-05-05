from __future__ import annotations

from app.scrapers.base import StoreScraper
from app.scrapers.fix_price import FixPriceScraper
from app.scrapers.magnit import MagnitScraper
from app.scrapers.pyaterochka import PyaterochkaScraper
from app.scrapers.smart import SmartScraper
from app.scrapers.spar import SparScraper
from app.scrapers.types import ScrapedProduct

SCRAPER_CLASSES: dict[str, type[StoreScraper]] = {
    "smart": SmartScraper,
    "magnit": MagnitScraper,
    "spar": SparScraper,
    "pyaterochka": PyaterochkaScraper,
    "fix_price": FixPriceScraper,
}


def get_scraper(store_slug: str) -> StoreScraper:
    try:
        return SCRAPER_CLASSES[store_slug]()
    except KeyError as exc:
        raise ValueError(f"unknown store scraper: {store_slug}") from exc


def list_scrapers() -> list[str]:
    return list(SCRAPER_CLASSES)


async def run_scraper(store_slug: str, limit: int | None = None) -> list[ScrapedProduct]:
    scraper = get_scraper(store_slug)
    try:
        return await scraper.scrape_catalog(limit=limit)
    finally:
        await scraper.close()

