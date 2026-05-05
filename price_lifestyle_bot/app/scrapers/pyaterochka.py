from __future__ import annotations

from urllib.parse import urlencode

from app.scrapers.base import HtmlSearchScraper


class PyaterochkaScraper(HtmlSearchScraper):
    store_slug = "pyaterochka"
    base_url = "https://5ka.ru"
    search_path = "/search/?q={query}"

    async def search_products(self, query: str):
        params = {"q": query}
        if self.settings.pyaterochka_city_id:
            params["city_id"] = self.settings.pyaterochka_city_id
        if self.settings.pyaterochka_store_id:
            params["store_id"] = self.settings.pyaterochka_store_id
        self.search_path = f"/search/?{urlencode(params)}"
        return await super().search_products(query)

