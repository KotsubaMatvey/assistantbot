from __future__ import annotations

from app.scrapers.base import HtmlSearchScraper


class SmartScraper(HtmlSearchScraper):
    store_slug = "smart"
    base_url = "https://smart.swnn.ru"
    search_path = "/search/?q={query}"

