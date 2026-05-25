from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.logging_config import get_logger

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import InlineKeyboardMarkup

    from app.services.assistant_jobs import AssistantJob
    from app.services.chat_dialogue import ChatButton
    from app.services.obsidian_memory import ObsidianMemory

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
        if settings.admin_backup_enabled:
            if settings.admin_telegram_ids:
                scheduler.add_job(
                    _send_admin_backup,
                    "interval",
                    hours=settings.admin_backup_interval_hours,
                    args=[bot],
                    id="send_admin_backup",
                    max_instances=1,
                    replace_existing=True,
                )
            else:
                logger.warning("scheduled_backup_disabled_without_admin_ids")
    return scheduler


async def _refresh_all_prices() -> None:
    from app.scripts.refresh_prices import refresh_all_prices

    try:
        result = await refresh_all_prices()
        if result.degraded_store_slugs:
            logger.warning(
                "scheduled_refresh_degraded",
                degraded_stores=result.degraded_store_slugs,
                failed_stores=result.failed_store_slugs,
                partial_stores=result.partial_store_slugs,
                products=result.total_products_found,
                prices=result.total_prices_found,
            )
    except Exception as exc:
        logger.exception("scheduled_refresh_failed", error=str(exc))


async def _send_due_reminders(bot: Bot) -> None:
    from app.services.audit_log import AuditLogStore
    from app.services.chat_dialogue import ChatDialogueEngine
    from app.services.obsidian_memory import ObsidianMemory
    from app.services.reminder_delivery import ReminderDeliveryStore

    settings = get_settings()
    memory = ObsidianMemory(settings.obsidian_vault_path)
    dialogue = ChatDialogueEngine(
        settings.obsidian_vault_path,
        timezone_name=getattr(settings, "timezone", "Europe/Moscow"),
    )
    deliveries = ReminderDeliveryStore(settings.obsidian_vault_path)
    audit = AuditLogStore(settings.obsidian_vault_path)
    for reminder in memory.due_reminders():
        delivery = deliveries.get(user_id=reminder.user_id, reminder_id=reminder.id)
        if delivery is not None and delivery.status == "sent":
            memory.mark_reminder_sent(reminder.path)
            continue
        if not deliveries.claim(user_id=reminder.user_id, reminder_id=reminder.id):
            continue
        try:
            reply = dialogue.delivered_reminder_reply(
                user_id=reminder.user_id,
                reminder_id=reminder.id,
                body=reminder.snippet,
            )
            await bot.send_message(
                reminder.user_id,
                f"Напоминание:\n{reminder.snippet}",
                reply_markup=_chat_markup(reply.rows),
            )
            deliveries.mark_sent(user_id=reminder.user_id, reminder_id=reminder.id)
            memory.mark_reminder_sent(reminder.path)
            audit.record(
                user_id=reminder.user_id,
                action="reminder_delivered",
                detail=reminder.id,
            )
        except Exception as exc:
            deliveries.mark_failed(
                user_id=reminder.user_id,
                reminder_id=reminder.id,
                error=str(exc),
            )
            audit.record(
                user_id=reminder.user_id,
                action="reminder_delivery_failed",
                detail=reminder.id,
            )
            logger.exception(
                "scheduled_reminder_failed",
                error=str(exc),
                reminder_id=reminder.id,
                user_id=reminder.user_id,
            )


async def _send_due_jobs(bot: Bot) -> None:
    from app.services.assistant_jobs import AssistantJobStore
    from app.services.obsidian_memory import ObsidianMemory

    settings = get_settings()
    jobs = AssistantJobStore(settings.obsidian_vault_path, timezone_name=settings.timezone)
    memory = ObsidianMemory(settings.obsidian_vault_path)
    for job in jobs.due_jobs():
        try:
            output = await _job_output(job, memory=memory)
            if output:
                if job.delivery_mode in {"morning", "evening"}:
                    await bot.send_message(
                        job.user_id,
                        output[:3900],
                        reply_markup=_daily_markup(),
                    )
                else:
                    await bot.send_message(job.user_id, output[:3900])
            jobs.record_run(job=job, ok=True, detail=_job_run_detail(job, output))
        except Exception as exc:
            jobs.record_run(job=job, ok=False, detail=str(exc))
            logger.exception(
                "scheduled_assistant_job_failed",
                error=str(exc),
                job_id=job.id,
                user_id=job.user_id,
            )


async def _send_admin_backup(bot: Bot) -> None:
    from aiogram.types import FSInputFile

    from app.services.admin_tools import create_backup, create_postgres_dump, repo_root_from_cwd
    from app.services.audit_log import AuditLogStore

    settings = get_settings()
    if not settings.admin_telegram_ids:
        return
    try:
        database_dump = await asyncio.to_thread(create_postgres_dump, settings.database_url)
        result = await asyncio.to_thread(
            create_backup,
            repo_root=repo_root_from_cwd(),
            vault_path=settings.obsidian_vault_path,
            database_dump=database_dump,
            encryption_key=settings.admin_backup_encryption_key,
        )
    except Exception as exc:
        logger.exception("scheduled_backup_failed", error=str(exc))
        return
    try:
        audit = AuditLogStore(settings.obsidian_vault_path)
        for admin_id in settings.admin_telegram_ids:
            try:
                await bot.send_document(
                    chat_id=admin_id,
                    document=FSInputFile(result.path),
                    caption=(
                        "Automatic backup. Store this sensitive archive securely. "
                        f"Files: {result.files_count}"
                    ),
                )
                audit.record(
                    user_id=admin_id,
                    action="scheduled_backup_delivered",
                    detail=f"files={result.files_count}",
                )
            except Exception as exc:
                audit.record(
                    user_id=admin_id,
                    action="scheduled_backup_delivery_failed",
                    detail=f"files={result.files_count}",
                )
                logger.exception(
                    "scheduled_backup_delivery_failed",
                    error=str(exc),
                    admin_id=admin_id,
                )
    finally:
        await asyncio.to_thread(result.path.unlink, missing_ok=True)


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
        from app.services.knowledge_ingestion import (
            fetch_feed_digests,
            format_digest_memory_note,
            format_feed_digests,
            list_rss_subscriptions,
        )

        subscriptions = list_rss_subscriptions(get_settings().obsidian_vault_path, user_id=user_id)
        if not subscriptions:
            return "RSS-подписок пока нет."
        digests = await fetch_feed_digests(subscriptions, limit_per_feed=3)
        memory.remember_user_note(user_id=user_id, text=format_digest_memory_note(digests))
        return format_feed_digests(digests)
    if delivery_mode == "doctor":
        return f"Doctor job:\n{message}"
    if delivery_mode == "markets":
        from app.services.market_watch import (
            fetch_market_watch,
            format_market_watch,
            market_watch_memory_note,
        )

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
    if delivery_mode == "evening":
        return _evening_output(user_id=user_id, memory=memory)
    return f"Запланированная задача:\n{message}"


def _job_run_detail(job: AssistantJob, output: str) -> str:
    sent = bool(output)
    return f"{job.delivery_mode}; sent={str(sent).lower()}; chars={min(len(output), 3900)}"


async def _price_alert_output(*, user_id: int) -> str:
    from sqlalchemy import select

    from app.db.models import User
    from app.db.repositories.prices import (
        get_latest_prices_by_store_products,
        get_price_history_stats,
    )
    from app.db.repositories.users import get_settings_for_user
    from app.db.session import SessionLocal
    from app.services.price_alerts import (
        PriceAlertStore,
        evaluate_price_alerts,
        format_price_alert_hits,
    )
    from app.services.price_comparator import offer_from_snapshot_with_history

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
        history = await get_price_history_stats(
            session,
            store_product_ids=[snapshot.store_product_id for snapshot in snapshots],
        )
    offers = [
        offer_from_snapshot_with_history(snapshot, history.get(snapshot.store_product_id))
        for snapshot in snapshots
    ]
    hits = evaluate_price_alerts(
        alerts,
        settings=user_settings,
        offers=offers,
        freshness_hours=settings.price_freshness_hours,
    )
    return format_price_alert_hits(hits)


async def _morning_output(*, user_id: int, memory: ObsidianMemory) -> str:
    from app.services.agenda import build_agenda
    from app.services.assistant_jobs import AssistantJobStore
    from app.services.daily_brief import DailyBrief, format_daily_brief
    from app.services.market_watch import fetch_market_watch, format_market_brief
    from app.services.pantry import PantryStore, format_pantry_suggestions
    from app.services.spending import SpendingStore, format_budget_summary

    settings = get_settings()
    markets = format_market_brief(await fetch_market_watch())
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
        notes=memory.lifestyle_focus_notes(user_id=user_id),
    )
    return format_daily_brief(brief)


def _evening_output(*, user_id: int, memory: ObsidianMemory) -> str:
    from app.services.spending import SpendingStore, format_budget_summary

    settings = get_settings()
    tasks = memory.list_open_tasks(user_id=user_id, limit=5)
    reminders = memory.list_reminders(user_id=user_id, limit=5)
    timezone = ZoneInfo(settings.timezone)
    lines = ["Evening review", "", "## Today", memory.today_digest(user_id=user_id)[:900]]
    lines.extend(["", "## Open tasks"])
    lines.extend(f"- {task.snippet} ({task.id})" for task in tasks)
    if not tasks:
        lines.append("- none")
    lines.extend(["", "## Reminders"])
    lines.extend(
        f"- {item.due_at.astimezone(timezone):%Y-%m-%d %H:%M}: {item.snippet}"
        for item in reminders
    )
    if not reminders:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Budget",
            format_budget_summary(
                SpendingStore(settings.obsidian_vault_path).budget_summary(user_id=user_id)
            ),
        ]
    )
    return "\n".join(lines)[:3900]


def _chat_markup(rows: tuple[tuple[ChatButton, ...], ...]) -> InlineKeyboardMarkup:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=str(button.text), callback_data=str(button.data))
                for button in row
            ]
            for row in rows
        ]
    )


def _daily_markup() -> InlineKeyboardMarkup:
    from app.services.chat_dialogue import daily_actions_keyboard

    return _chat_markup(daily_actions_keyboard())
