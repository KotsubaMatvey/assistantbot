from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PriceSnapshot, ScrapeRun, Store, StoreProduct


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def human_age(value: datetime | None, *, now: datetime | None = None) -> str:
    if value is None:
        return "нет данных"
    base = now or datetime.now(UTC)
    delta = max(base - _aware(value), timedelta())
    minutes = int(delta.total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} мин назад"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} ч назад"
    return f"{hours // 24} д назад"


@dataclass(frozen=True)
class StorePriceHealth:
    slug: str
    display_name: str
    parser_status: str
    products_count: int
    priced_products_count: int
    snapshots_count: int
    latest_price_at: datetime | None
    last_scrape_finished_at: datetime | None
    last_scrape_status: str | None
    last_scrape_error: str | None
    freshness_hours: int

    @property
    def has_prices(self) -> bool:
        return self.priced_products_count > 0 and self.latest_price_at is not None

    @property
    def is_stale(self) -> bool:
        if self.latest_price_at is None:
            return True
        return _aware(self.latest_price_at) < datetime.now(UTC) - timedelta(
            hours=self.freshness_hours
        )

    @property
    def status_label(self) -> str:
        if not self.has_prices:
            return "нет цен"
        if self.is_stale:
            return "устарело"
        return "свежие"


@dataclass(frozen=True)
class CatalogHealth:
    stores: list[StorePriceHealth]
    freshness_hours: int

    @property
    def fresh_store_count(self) -> int:
        return sum(1 for store in self.stores if store.has_prices and not store.is_stale)

    @property
    def stale_store_count(self) -> int:
        return sum(1 for store in self.stores if store.has_prices and store.is_stale)

    @property
    def empty_store_count(self) -> int:
        return sum(1 for store in self.stores if not store.has_prices)


async def get_catalog_health(session: AsyncSession, *, freshness_hours: int) -> CatalogHealth:
    stores_result = await session.execute(select(Store).order_by(Store.slug))
    stores = list(stores_result.scalars())

    product_rows = await session.execute(
        select(Store.slug, func.count(StoreProduct.id))
        .select_from(Store)
        .join(StoreProduct, StoreProduct.store_id == Store.id, isouter=True)
        .group_by(Store.slug)
    )
    products_by_store = {slug: count for slug, count in product_rows}

    price_rows = await session.execute(
        select(
            Store.slug,
            func.count(func.distinct(PriceSnapshot.store_product_id)),
            func.count(PriceSnapshot.id),
            func.max(PriceSnapshot.scraped_at),
        )
        .select_from(Store)
        .join(StoreProduct, StoreProduct.store_id == Store.id, isouter=True)
        .join(PriceSnapshot, PriceSnapshot.store_product_id == StoreProduct.id, isouter=True)
        .group_by(Store.slug)
    )
    prices_by_store = {
        slug: (priced_count, snapshots_count, latest_at)
        for slug, priced_count, snapshots_count, latest_at in price_rows
    }

    health: list[StorePriceHealth] = []
    for store in stores:
        last_run = await session.scalar(
            select(ScrapeRun)
            .where(ScrapeRun.store_id == store.id)
            .order_by(desc(ScrapeRun.finished_at), desc(ScrapeRun.started_at))
            .limit(1)
        )
        priced_count, snapshots_count, latest_at = prices_by_store.get(store.slug, (0, 0, None))
        health.append(
            StorePriceHealth(
                slug=store.slug,
                display_name=store.display_name,
                parser_status=store.parser_status.value,
                products_count=products_by_store.get(store.slug, 0),
                priced_products_count=priced_count,
                snapshots_count=snapshots_count,
                latest_price_at=latest_at,
                last_scrape_finished_at=last_run.finished_at if last_run else None,
                last_scrape_status=last_run.status.value if last_run else None,
                last_scrape_error=last_run.error_message if last_run else None,
                freshness_hours=freshness_hours,
            )
        )
    return CatalogHealth(stores=health, freshness_hours=freshness_hours)


def format_catalog_health(health: CatalogHealth) -> str:
    lines = [
        "Статус цен",
        f"Порог свежести: {health.freshness_hours} ч",
        (
            f"Магазины: свежие {health.fresh_store_count}, "
            f"устаревшие {health.stale_store_count}, без цен {health.empty_store_count}"
        ),
        "",
    ]
    for store in health.stores:
        lines.append(
            f"{store.display_name} ({store.slug}): {store.status_label}, "
            f"товаров {store.products_count}, с ценами {store.priced_products_count}, "
            f"снимков {store.snapshots_count}, последняя цена {human_age(store.latest_price_at)}"
        )
        scrape_age = human_age(store.last_scrape_finished_at)
        scrape_status = store.last_scrape_status or "нет запуска"
        lines.append(
            f"  scraper: {store.parser_status}, последний запуск {scrape_status}, {scrape_age}"
        )
        if store.last_scrape_error:
            lines.append(f"  ошибка: {store.last_scrape_error[:200]}")
    return "\n".join(lines)
