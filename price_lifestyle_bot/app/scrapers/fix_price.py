from __future__ import annotations

from urllib.parse import urlencode

from app.scrapers.base import HtmlSearchScraper
from app.scrapers.types import ScrapedProduct


class FixPriceScraper(HtmlSearchScraper):
    store_slug = "fix_price"
    base_url = "https://fix-price.com"
    search_path = "/search/?q={query}"

    async def search_products(self, query: str) -> list[ScrapedProduct]:
        params = {"q": query}
        if self.settings.fix_price_city:
            params["city"] = self.settings.fix_price_city
        self.search_path = f"/search/?{urlencode(params)}"
        return await super().search_products(query)
