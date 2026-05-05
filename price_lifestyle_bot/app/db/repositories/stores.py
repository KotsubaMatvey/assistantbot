from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ParserStatus, ScrapeRun, ScrapeRunStatus, Store

DEFAULT_STORES = [
    {
        "slug": "smart",
        "chain_name": "Smart / Сладкая жизнь",
        "display_name": "Smart",
        "website_url": "https://smart.swnn.ru",
        "parser_status": ParserStatus.partial,
    },
    {
        "slug": "magnit",
        "chain_name": "Магнит",
        "display_name": "Магнит",
        "website_url": "https://magnit.ru",
        "parser_status": ParserStatus.partial,
    },
    {
        "slug": "spar",
        "chain_name": "SPAR / EUROSPAR",
        "display_name": "SPAR",
        "website_url": "https://myspar.ru",
        "parser_status": ParserStatus.partial,
    },
    {
        "slug": "pyaterochka",
        "chain_name": "Пятёрочка",
        "display_name": "Пятёрочка",
        "website_url": "https://5ka.ru",
        "parser_status": ParserStatus.partial,
    },
    {
        "slug": "fix_price",
        "chain_name": "Fix Price",
        "display_name": "Fix Price",
        "website_url": "https://fix-price.com",
        "parser_status": ParserStatus.partial,
    },
]


async def seed_stores(session: AsyncSession, city: str) -> None:
    for store in DEFAULT_STORES:
        stmt = (
            insert(Store)
            .values(city=city, is_enabled=True, **store)
            .on_conflict_do_update(
                index_elements=[Store.slug],
                set_={
                    "chain_name": store["chain_name"],
                    "display_name": store["display_name"],
                    "website_url": store["website_url"],
                    "parser_status": store["parser_status"],
                    "is_enabled": True,
                },
            )
        )
        await session.execute(stmt)


async def get_store_by_slug(session: AsyncSession, slug: str) -> Store | None:
    result = await session.execute(select(Store).where(Store.slug == slug))
    return result.scalar_one_or_none()


async def list_enabled_stores(session: AsyncSession, slugs: list[str] | None = None) -> list[Store]:
    stmt = select(Store).where(Store.is_enabled.is_(True))
    if slugs is not None:
        stmt = stmt.where(Store.slug.in_(slugs))
    result = await session.execute(stmt.order_by(Store.id))
    return list(result.scalars())


async def create_scrape_run(session: AsyncSession, store_id: int) -> ScrapeRun:
    run = ScrapeRun(store_id=store_id, status=ScrapeRunStatus.started)
    session.add(run)
    await session.flush()
    return run


async def finish_scrape_run(
    session: AsyncSession,
    run: ScrapeRun,
    *,
    status: ScrapeRunStatus,
    products_found: int,
    prices_found: int,
    error_message: str | None = None,
) -> ScrapeRun:
    run.status = status
    run.finished_at = datetime.now(UTC)
    run.products_found = products_found
    run.prices_found = prices_found
    run.error_message = error_message
    await session.flush()
    return run
