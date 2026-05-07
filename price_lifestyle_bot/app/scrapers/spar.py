from __future__ import annotations

from urllib.parse import urlencode

from app.scrapers.base import HtmlSearchScraper
from app.scrapers.types import ScrapedProduct


class SparScraper(HtmlSearchScraper):
    store_slug = "spar"
    base_url = "https://myspar.ru"
    search_path = "/search/?q={query}"

    async def search_products(self, query: str) -> list[ScrapedProduct]:
        params = {"q": query}
        if self.settings.spar_region:
            params["region"] = self.settings.spar_region
        self.search_path = f"/search/?{urlencode(params)}"
        return await super().search_products(query)
