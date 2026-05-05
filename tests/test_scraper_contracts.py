from __future__ import annotations

import asyncio

import pytest

from app.db.models import PriceType
from app.scrapers.registry import SCRAPER_CLASSES
from app.scrapers.types import ScrapedProduct

HTML = """
<html><body>
  <article data-product-id="1">
    <a href="/p/1"><h3>Молоко 2.5% 1 л</h3></a>
    <span>89.90 ₽</span>
  </article>
</body></html>
"""


class FakeResponse:
    text = HTML


@pytest.mark.parametrize("slug,scraper_cls", SCRAPER_CLASSES.items())
def test_scraper_search_contract_without_network(monkeypatch, slug, scraper_cls) -> None:
    async def fake_get(self, url):  # noqa: ANN001
        return FakeResponse()

    monkeypatch.setattr(scraper_cls, "get", fake_get)
    products = asyncio.run(_run_search(scraper_cls))
    assert isinstance(products, list)
    assert all(isinstance(product, ScrapedProduct) for product in products)
    assert products[0].price_type in {
        PriceType.regular,
        PriceType.promo,
        PriceType.card,
        PriceType.promo_card,
        PriceType.unknown,
    }


async def _run_search(scraper_cls):  # noqa: ANN001
    scraper = scraper_cls()
    try:
        return await scraper.search_products("молоко")
    finally:
        await scraper.close()
