from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import desc, select, text

from app.config import get_settings
from app.db.models import ScrapeRun, Store
from app.db.session import SessionLocal
from app.scripts.refresh_prices import refresh_all_prices
from app.scripts.scrape_once import scrape_store
from app.services.admin_tools import (
    CheckResult,
    check_docker_compose,
    check_secret_files,
    check_vault,
    create_backup,
    format_checks,
    repo_root_from_cwd,
)
from app.services.price_health import format_catalog_health, get_catalog_health
from app.services.scraper_diagnostics import diagnose_scraper, format_scraper_diagnostic

router = Router()


def _is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in set(get_settings().admin_telegram_ids)


@router.message(Command("admin_refresh_prices"))
async def admin_refresh_prices(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    await message.answer("Запускаю обновление цен.")
    await refresh_all_prices()
    await message.answer("Обновление цен завершено.")


@router.message(Command("admin_scrape_store"))
async def admin_scrape_store(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    store_slug = (message.text or "").partition(" ")[2].strip()
    if not store_slug:
        await message.answer("Использование: /admin_scrape_store <store_slug>")
        return
    products, prices = await scrape_store(store_slug)
    await message.answer(f"{store_slug}: товаров {products}, цен {prices}")


@router.message(Command("admin_status"))
async def admin_status(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    settings = get_settings()
    async with SessionLocal() as session:
        health = await get_catalog_health(
            session,
            freshness_hours=settings.price_freshness_hours,
        )
    await message.answer(format_catalog_health(health))


@router.message(Command("admin_diag"))
async def admin_diag(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    settings = get_settings()
    repo_root = repo_root_from_cwd()
    checks = [
        check_vault(settings.obsidian_vault_path),
        check_secret_files(repo_root),
        await _db_check(),
        await _redis_check(settings.redis_url),
        *check_docker_compose(repo_root),
    ]
    await message.answer("Диагностика\n" + format_checks(checks))


@router.message(Command("admin_backup"))
async def admin_backup(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    settings = get_settings()
    result = create_backup(
        repo_root=repo_root_from_cwd(),
        vault_path=settings.obsidian_vault_path,
    )
    await message.answer(f"Backup создан: {result.path}\nФайлов: {result.files_count}")


@router.message(Command("admin_deploy_check"))
async def admin_deploy_check(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    repo_root = repo_root_from_cwd()
    checks = [
        check_secret_files(repo_root),
        *check_docker_compose(repo_root),
    ]
    await message.answer("Deploy check\n" + format_checks(checks))


@router.message(Command("admin_logs"))
async def admin_logs(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    async with SessionLocal() as session:
        rows = await session.execute(
            select(Store.slug, ScrapeRun.status, ScrapeRun.finished_at, ScrapeRun.error_message)
            .join(Store, Store.id == ScrapeRun.store_id)
            .where(ScrapeRun.error_message.is_not(None))
            .order_by(desc(ScrapeRun.finished_at), desc(ScrapeRun.started_at))
            .limit(10)
        )
    lines = ["Последние ошибки scraping"]
    found = False
    for slug, status, finished_at, error in rows:
        found = True
        status_value = status.value if hasattr(status, "value") else str(status)
        lines.append(f"- {slug} {status_value} {finished_at}: {str(error)[:300]}")
    if not found:
        lines.append("Ошибок scraping в базе не найдено.")
    await message.answer("\n".join(lines))


@router.message(Command("admin_scraper_diag"))
async def admin_scraper_diag(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    args = (message.text or "").split(maxsplit=2)
    if len(args) < 2:
        await message.answer("Использование: /admin_scraper_diag <store_slug> [query]")
        return
    store_slug = args[1]
    query = args[2] if len(args) > 2 else "молоко"
    try:
        result = await diagnose_scraper(store_slug, query=query)
    except Exception as exc:
        await message.answer(f"Диагностика не запустилась: {str(exc)[:300]}")
        return
    await message.answer(format_scraper_diagnostic(result))


async def _db_check() -> CheckResult:
    try:
        async with SessionLocal() as session:
            await session.execute(text("select 1"))
        return CheckResult("Postgres", True, "select 1 ok")
    except Exception as exc:
        return CheckResult("Postgres", False, str(exc))


async def _redis_check(redis_url: str) -> CheckResult:
    try:
        from redis.asyncio import Redis

        client = Redis.from_url(redis_url)
        try:
            await client.ping()
        finally:
            await client.aclose()
        return CheckResult("Redis", True, "ping ok")
    except Exception as exc:
        return CheckResult("Redis", False, str(exc))
