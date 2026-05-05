from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


def create_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _refresh_all_prices,
        "interval",
        hours=settings.scrape_interval_hours,
        id="refresh_prices",
        replace_existing=True,
    )
    return scheduler


async def _refresh_all_prices() -> None:
    from app.scripts.refresh_prices import refresh_all_prices

    try:
        await refresh_all_prices()
    except Exception as exc:
        logger.exception("scheduled_refresh_failed", error=str(exc))

