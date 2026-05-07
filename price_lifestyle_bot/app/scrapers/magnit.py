from __future__ import annotations

from urllib.parse import urlencode

from app.scrapers.base import HtmlSearchScraper
from app.scrapers.types import ScrapedProduct


class MagnitScraper(HtmlSearchScraper):
    store_slug = "magnit"
    base_url = "https://magnit.ru"
    search_path = "/search/?q={query}"

    async def search_products(self, query: str) -> list[ScrapedProduct]:
        params = {"q": query}
        if self.settings.magnit_shop_code:
            params["shopCode"] = self.settings.magnit_shop_code
        if self.settings.magnit_shop_type:
            params["shopType"] = self.settings.magnit_shop_type
        self.search_path = f"/search/?{urlencode(params)}"
        return await super().search_products(query)
