from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import PriceSnapshot, PriceSource, PriceType, StoreProduct


@dataclass(frozen=True)
class PriceHistoryStats:
    store_product_id: int
    samples_count: int
    average_price: Decimal
    min_price: Decimal
    max_price: Decimal


async def add_price_snapshot(
    session: AsyncSession,
    *,
    store_product_id: int,
    final_price: Decimal,
    price_type: PriceType,
    source: PriceSource,
    scraped_at: datetime,
    regular_price: Decimal | None = None,
    old_price: Decimal | None = None,
    promo_price: Decimal | None = None,
    card_price: Decimal | None = None,
    unit_price: Decimal | None = None,
    unit_price_unit: str | None = None,
    in_stock: bool | None = None,
) -> PriceSnapshot:
    snapshot = PriceSnapshot(
        store_product_id=store_product_id,
        regular_price=regular_price,
        old_price=old_price,
        promo_price=promo_price,
        card_price=card_price,
        final_price=final_price,
        price_type=price_type,
        currency="RUB",
        unit_price=unit_price,
        unit_price_unit=unit_price_unit,
        in_stock=in_stock,
        source=source,
        scraped_at=scraped_at,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


async def get_latest_prices_by_store_products(
    session: AsyncSession,
    store_product_ids: Sequence[int] | None = None,
) -> list[PriceSnapshot]:
    row_number = (
        func.row_number()
        .over(partition_by=PriceSnapshot.store_product_id, order_by=desc(PriceSnapshot.scraped_at))
        .label("row_number")
    )
    subquery: Select[tuple[int, int]] = select(PriceSnapshot.id, row_number)
    if store_product_ids is not None:
        subquery = subquery.where(PriceSnapshot.store_product_id.in_(store_product_ids))
    ranked = subquery.subquery()
    result = await session.execute(
        select(PriceSnapshot)
        .join(ranked, ranked.c.id == PriceSnapshot.id)
        .where(ranked.c.row_number == 1)
        .options(selectinload(PriceSnapshot.store_product).selectinload(StoreProduct.store))
    )
    return list(result.scalars())


async def get_price_history_stats(
    session: AsyncSession,
    *,
    store_product_ids: Sequence[int] | None = None,
    days: int = 30,
) -> dict[int, PriceHistoryStats]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    stmt = (
        select(
            PriceSnapshot.store_product_id,
            func.count(PriceSnapshot.id),
            func.avg(PriceSnapshot.final_price),
            func.min(PriceSnapshot.final_price),
            func.max(PriceSnapshot.final_price),
        )
        .where(PriceSnapshot.scraped_at >= cutoff)
        .group_by(PriceSnapshot.store_product_id)
    )
    if store_product_ids is not None:
        stmt = stmt.where(PriceSnapshot.store_product_id.in_(store_product_ids))
    rows = await session.execute(stmt)
    return {
        store_product_id: PriceHistoryStats(
            store_product_id=store_product_id,
            samples_count=int(samples_count),
            average_price=Decimal(str(average_price)),
            min_price=Decimal(str(min_price)),
            max_price=Decimal(str(max_price)),
        )
        for store_product_id, samples_count, average_price, min_price, max_price in rows
        if average_price is not None and min_price is not None and max_price is not None
    }
