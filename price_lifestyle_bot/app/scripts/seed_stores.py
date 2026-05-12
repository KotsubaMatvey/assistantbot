from __future__ import annotations

import asyncio

from app.config import get_settings
from app.db.repositories.stores import seed_stores
from app.db.session import SessionLocal, dispose_engine


async def main() -> None:
    try:
        async with SessionLocal() as session:
            await seed_stores(session, get_settings().city)
            await session.commit()
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
