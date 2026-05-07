from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.config import get_settings
from app.db.models import PriceType
from app.logging_config import get_logger
from app.scrapers.types import ScrapedProduct
from app.services.product_normalizer import calculate_unit_price, extract_quantity

logger = get_logger(__name__)

PRICE_RE = re.compile(r"(?P<price>\d+(?:[\s\u00a0]?\d{3})*(?:[.,]\d{1,2})?)\s*(₽|руб)", re.I)
USER_AGENT = "PriceLifestyleBot/0.1 (+https://github.com/KotsubaMatvey/assistantbot)"


class StoreScraper(ABC):
    store_slug: str
    base_url: str

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ru-RU,ru;q=0.9"},
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def get(self, url: str) -> httpx.Response:
        delay = 0.5
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                return response
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "scraper_request_failed",
                    store_slug=self.store_slug,
                    url=url,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                await asyncio.sleep(delay)
                delay *= 2
        raise RuntimeError(f"request failed: {last_exc}")

    @abstractmethod
    async def search_products(self, query: str) -> list[ScrapedProduct]:
        raise NotImplementedError

    @abstractmethod
    async def scrape_catalog(self, limit: int | None = None) -> list[ScrapedProduct]:
        raise NotImplementedError

    @abstractmethod
    async def scrape_product(self, url: str) -> ScrapedProduct | None:
        raise NotImplementedError

    async def playwright_fallback(self, url: str) -> str | None:
        if not self.settings.enable_playwright:
            return None
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("playwright_not_installed", store_slug=self.store_slug)
            return None
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=USER_AGENT)
            await page.goto(url, wait_until="networkidle", timeout=20000)
            html = await page.content()
            await browser.close()
            return html


class HtmlSearchScraper(StoreScraper):
    search_path: str = "/search/?q={query}"
    seed_queries: tuple[str, ...] = ("молоко", "яйца", "сахар", "кофе", "бананы")

    async def search_products(self, query: str) -> list[ScrapedProduct]:
        url = urljoin(self.base_url, self.search_path.format(query=quote(query)))
        try:
            response = await self.get(url)
            products = self.extract_products_from_html(response.text, url)
            if products:
                return products
            html = await self.playwright_fallback(url)
            return self.extract_products_from_html(html, url) if html else []
        except Exception as exc:
            logger.exception("scraper_search_failed", store_slug=self.store_slug, error=str(exc))
            return []

    async def scrape_catalog(self, limit: int | None = None) -> list[ScrapedProduct]:
        products: list[ScrapedProduct] = []
        for query in self.seed_queries:
            products.extend(await self.search_products(query))
            if limit is not None and len(products) >= limit:
                return products[:limit]
            await asyncio.sleep(0.3)
        return products

    async def scrape_product(self, url: str) -> ScrapedProduct | None:
        try:
            response = await self.get(url)
            products = self.extract_products_from_html(response.text, url)
            return products[0] if products else None
        except Exception as exc:
            logger.exception(
                "scraper_product_failed",
                store_slug=self.store_slug,
                url=url,
                error=str(exc),
            )
            return None

    def extract_products_from_html(self, html: str, page_url: str) -> list[ScrapedProduct]:
        soup = BeautifulSoup(html, "html.parser")
        cards: list[Tag] = list(
            soup.select("[data-product-id], article, .product, .catalog-item, .product-card")
        )
        if not cards:
            cards = [
                tag.parent
                for tag in soup.find_all(string=PRICE_RE)
                if isinstance(tag.parent, Tag)
            ]

        products: list[ScrapedProduct] = []
        seen: set[str] = set()
        for card in cards:
            text = " ".join(card.get_text(" ", strip=True).split())
            price = parse_price(text)
            if price is None:
                continue
            title = self._extract_title(card, text)
            if not title or len(title) < 3:
                continue
            link = card.find("a", href=True)
            href = link.get("href") if isinstance(link, Tag) else None
            source_url = urljoin(page_url, href) if isinstance(href, str) else page_url
            key = f"{title}:{price}:{source_url}"
            if key in seen:
                continue
            seen.add(key)
            quantity_value, quantity_unit = extract_quantity(title)
            unit_price, unit_price_unit = calculate_unit_price(price, quantity_value, quantity_unit)
            price_type = detect_price_type(text)
            regular_price = price if price_type == PriceType.regular else None
            promo_price = price if price_type == PriceType.promo else None
            card_price = price if price_type in {PriceType.card, PriceType.promo_card} else None
            external_id = _string_attr(card.get("data-product-id"))
            products.append(
                ScrapedProduct(
                    external_id=external_id,
                    title=title,
                    source_url=source_url,
                    regular_price=regular_price,
                    promo_price=promo_price,
                    card_price=card_price,
                    final_price=price,
                    price_type=price_type,
                    quantity_value=quantity_value,
                    quantity_unit=quantity_unit,
                    unit_price=unit_price,
                    unit_price_unit=unit_price_unit,
                    raw_payload={"text": text[:1000]},
                )
            )
        return products

    def _extract_title(self, card: Tag, text: str) -> str:
        for selector in ["[itemprop=name]", ".title", ".name", "h1", "h2", "h3", "a"]:
            found = card.select_one(selector) if hasattr(card, "select_one") else None
            if found:
                title = found.get_text(" ", strip=True)
                if title:
                    return title
        price_match = PRICE_RE.search(text)
        return text[: price_match.start()].strip(" -–") if price_match else text[:120]


def _string_attr(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def parse_price(value: str) -> Decimal | None:
    match = PRICE_RE.search(value)
    if not match:
        return None
    normalized = match.group("price").replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(normalized).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def detect_price_type(text: str) -> PriceType:
    lowered = text.lower()
    has_card = "карт" in lowered
    has_promo = any(marker in lowered for marker in ("акци", "скид", "спеццен"))
    if has_card and has_promo:
        return PriceType.promo_card
    if has_card:
        return PriceType.card
    if has_promo:
        return PriceType.promo
    return PriceType.regular
