from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Store, StoreProduct


async def upsert_store_product(
    session: AsyncSession,
    *,
    store_id: int,
    raw_title: str,
    normalized_title: str,
    external_id: str | None = None,
    source_url: str | None = None,
    brand: str | None = None,
    category: str | None = None,
    quantity_value: Decimal | None = None,
    quantity_unit: str | None = None,
    barcode: str | None = None,
) -> StoreProduct:
    stmt = select(StoreProduct).where(
        StoreProduct.store_id == store_id,
        StoreProduct.external_id == external_id,
        StoreProduct.raw_title == raw_title,
    )
    result = await session.execute(stmt)
    product = result.scalar_one_or_none()
    if product is None:
        product = StoreProduct(
            store_id=store_id,
            external_id=external_id,
            source_url=source_url,
            raw_title=raw_title,
            normalized_title=normalized_title,
            brand=brand,
            category=category,
            quantity_value=quantity_value,
            quantity_unit=quantity_unit,
            barcode=barcode,
            is_active=True,
        )
        session.add(product)
    else:
        product.source_url = source_url
        product.normalized_title = normalized_title
        product.brand = brand
        product.category = category
        product.quantity_value = quantity_value
        product.quantity_unit = quantity_unit
        product.barcode = barcode
        product.is_active = True
    await session.flush()
    return product


async def list_store_products(session: AsyncSession, store_slugs: list[str]) -> list[StoreProduct]:
    stmt = (
        select(StoreProduct)
        .join(Store, Store.id == StoreProduct.store_id)
        .where(StoreProduct.is_active.is_(True), Store.slug.in_(store_slugs))
    )
    result = await session.execute(stmt)
    return list(result.scalars())
