from __future__ import annotations

import time
from dataclasses import dataclass

from app.scrapers.registry import get_scraper


@dataclass(frozen=True)
class ScraperDiagnostic:
    store_slug: str
    query: str
    ok: bool
    elapsed_ms: int
    products_count: int
    sample_titles: list[str]
    error_message: str | None = None


async def diagnose_scraper(store_slug: str, *, query: str = "молоко") -> ScraperDiagnostic:
    started = time.perf_counter()
    scraper = get_scraper(store_slug)
    products_count = 0
    sample_titles: list[str] = []
    error_message: str | None = None
    ok = True
    try:
        products = await scraper.search_products(query)
        products_count = len(products)
        sample_titles = [product.title for product in products[:5]]
    except Exception as exc:
        ok = False
        error_message = str(exc)
    finally:
        await scraper.close()
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return ScraperDiagnostic(
        store_slug=store_slug,
        query=query,
        ok=ok,
        elapsed_ms=elapsed_ms,
        products_count=products_count,
        sample_titles=sample_titles,
        error_message=error_message,
    )


def format_scraper_diagnostic(result: ScraperDiagnostic) -> str:
    status = "OK" if result.ok else "FAIL"
    lines = [
        f"Scraper diagnostic: {result.store_slug}",
        f"Статус: {status}",
        f"Запрос: {result.query}",
        f"Время: {result.elapsed_ms} мс",
        f"Найдено товаров: {result.products_count}",
    ]
    if result.error_message:
        lines.append(f"Ошибка: {result.error_message[:500]}")
    if result.sample_titles:
        lines.append("Примеры:")
        lines.extend(f"- {title}" for title in result.sample_titles)
    return "\n".join(lines)
