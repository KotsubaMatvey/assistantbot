from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import get_settings
from app.db.models import User
from app.db.repositories.prices import get_latest_prices_by_store_products
from app.db.repositories.users import get_settings_for_user
from app.db.session import SessionLocal
from app.logging_config import get_logger
from app.services.agenda import build_agenda
from app.services.assistant_jobs import AssistantJob, AssistantJobStore
from app.services.daily_brief import DailyBrief, format_daily_brief
from app.services.knowledge_ingestion import (
    fetch_feed_digests,
    format_digest_memory_note,
    format_feed_digests,
    list_rss_subscriptions,
)
from app.services.market_watch import (
    fetch_market_watch,
    format_market_watch,
    market_watch_memory_note,
)
from app.services.obsidian_memory import ObsidianMemory
from app.services.pantry import PantryStore, format_pantry_suggestions
from app.services.price_alerts import (
    PriceAlertStore,
    evaluate_price_alerts,
    format_price_alert_hits,
)
from app.services.price_comparator import offer_from_snapshot
from app.services.spending import SpendingStore, format_budget_summary

if TYPE_CHECKING:
    from aiogram import Bot

logger = get_logger(__name__)


def create_scheduler(bot: Bot | None = None) -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _refresh_all_prices,
        "interval",
        hours=settings.scrape_interval_hours,
        id="refresh_prices",
        replace_existing=True,
    )
    if bot is not None:
        scheduler.add_job(
            _send_due_reminders,
            "interval",
            minutes=1,
            args=[bot],
            id="send_due_reminders",
            max_instances=1,
            replace_existing=True,
        )
        scheduler.add_job(
            _send_due_jobs,
            "interval",
            minutes=1,
            args=[bot],
            id="send_due_jobs",
            max_instances=1,
            replace_existing=True,
        )
    return scheduler


async def _refresh_all_prices() -> None:
    from app.scripts.refresh_prices import refresh_all_prices

    try:
        await refresh_all_prices()
    except Exception as exc:
        logger.exception("scheduled_refresh_failed", error=str(exc))


async def _send_due_reminders(bot: Bot) -> None:
    settings = get_settings()
    memory = ObsidianMemory(settings.obsidian_vault_path)
    for reminder in memory.due_reminders():
        try:
            await bot.send_message(reminder.user_id, f"Напоминание:\n{reminder.snippet}")
            memory.mark_reminder_sent(reminder.path)
        except Exception as exc:
            logger.exception(
                "scheduled_reminder_failed",
                error=str(exc),
                reminder_id=reminder.id,
                user_id=reminder.user_id,
            )


async def _send_due_jobs(bot: Bot) -> None:
    settings = get_settings()
    jobs = AssistantJobStore(settings.obsidian_vault_path, timezone_name=settings.timezone)
    memory = ObsidianMemory(settings.obsidian_vault_path)
    for job in jobs.due_jobs():
        try:
            output = await _job_output(job, memory=memory)
            if output:
                await bot.send_message(job.user_id, output[:3900])
            jobs.record_run(job=job, ok=True, detail=job.delivery_mode)
        except Exception as exc:
            jobs.record_run(job=job, ok=False, detail=str(exc))
            logger.exception(
                "scheduled_assistant_job_failed",
                error=str(exc),
                job_id=job.id,
                user_id=job.user_id,
            )


async def _job_output(job: AssistantJob, *, memory: ObsidianMemory) -> str:
    delivery_mode = job.delivery_mode
    user_id = job.user_id
    message = job.message
    if delivery_mode == "silent":
        memory.remember_user_note(
            user_id=user_id,
            text=message,
            note_type="job",
            extra_tags=["job"],
        )
        return ""
    if delivery_mode == "digest":
        return memory.period_digest(user_id=user_id, days=7)
    if delivery_mode == "rss":
        subscriptions = list_rss_subscriptions(get_settings().obsidian_vault_path, user_id=user_id)
        if not subscriptions:
            return "RSS-подписок пока нет."
        digests = await fetch_feed_digests(subscriptions, limit_per_feed=3)
        memory.remember_user_note(user_id=user_id, text=format_digest_memory_note(digests))
        return format_feed_digests(digests)
    if delivery_mode == "doctor":
        return f"Doctor job:\n{message}"
    if delivery_mode == "markets":
        result = await fetch_market_watch()
        memory.remember_user_note(
            user_id=user_id,
            text=market_watch_memory_note(result),
            note_type="market",
            extra_tags=["market", "prices"],
        )
        return format_market_watch(result)
    if delivery_mode == "price_alerts":
        return await _price_alert_output(user_id=user_id)
    if delivery_mode == "morning":
        return await _morning_output(user_id=user_id, memory=memory)
    return f"Запланированная задача:\n{message}"


async def _price_alert_output(*, user_id: int) -> str:
    settings = get_settings()
    alerts = PriceAlertStore(settings.obsidian_vault_path).list_alerts(user_id=user_id)
    if not alerts:
        return "Price alerts пока нет."
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == user_id))
        user_settings = (
            await get_settings_for_user(session, user.id)
            if user is not None
            else SimpleNamespace(enabled_store_slugs=[], comparison_mode="mixed")
        )
        snapshots = await get_latest_prices_by_store_products(session)
    offers = [offer_from_snapshot(snapshot) for snapshot in snapshots]
    hits = evaluate_price_alerts(
        alerts,
        settings=user_settings,
        offers=offers,
        freshness_hours=settings.price_freshness_hours,
    )
    return format_price_alert_hits(hits)


async def _morning_output(*, user_id: int, memory: ObsidianMemory) -> str:
    settings = get_settings()
    markets = format_market_watch(await fetch_market_watch())
    agenda = build_agenda(
        memory=memory,
        jobs=AssistantJobStore(settings.obsidian_vault_path, timezone_name=settings.timezone),
        user_id=user_id,
        timezone_name=settings.timezone,
    )
    pantry = format_pantry_suggestions(
        PantryStore(settings.obsidian_vault_path).shopping_suggestions(user_id=user_id)
    )
    budget = format_budget_summary(
        SpendingStore(settings.obsidian_vault_path).budget_summary(user_id=user_id)
    )
    brief = DailyBrief(
        agenda=agenda,
        markets=markets,
        price_alerts=await _price_alert_output(user_id=user_id),
        pantry=pantry,
        budget=budget,
    )
    return format_daily_brief(brief)
