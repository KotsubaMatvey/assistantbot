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
from app.services.access_control import AccessControlStore
from app.services.admin_tools import (
    CheckResult,
    check_access_control,
    check_docker_compose,
    check_memory_index,
    check_secret_files,
    check_vault,
    create_backup,
    format_checks,
    format_health_score,
    repo_root_from_cwd,
    security_audit_checks,
)
from app.services.audit_log import AuditLogStore
from app.services.obsidian_memory import ObsidianMemory
from app.services.price_health import format_catalog_health, get_catalog_health
from app.services.scraper_diagnostics import diagnose_scraper, format_scraper_diagnostic
from app.services.secret_scanner import format_secret_findings, scan_for_secrets

router = Router()


def _is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in set(get_settings().admin_telegram_ids)


@router.message(Command("admin_refresh_prices"))
async def admin_refresh_prices(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    await message.answer("Запускаю обновление цен.")
    result = await refresh_all_prices()
    if result.degraded_store_slugs:
        await message.answer(
            "Обновление цен завершено с деградацией: "
            + ", ".join(result.degraded_store_slugs)
        )
        return
    await message.answer("Обновление цен завершено.")


@router.message(Command("admin_scrape_store"))
async def admin_scrape_store(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    store_slug = (message.text or "").partition(" ")[2].strip()
    if not store_slug:
        await message.answer("Использование: /admin_scrape_store <store_slug>")
        return
    result = await scrape_store(store_slug)
    suffix = f", причина: {result.error_message}" if result.error_message else ""
    await message.answer(
        f"{store_slug}: {result.status.value}, товаров {result.products_found}, "
        f"цен {result.prices_found}{suffix}"
    )


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
        check_memory_index(settings.obsidian_vault_path),
        check_access_control(settings.obsidian_vault_path, settings.assistant_access_mode),
        *security_audit_checks(settings=settings, repo_root=repo_root),
        await _db_check(),
        await _redis_check(settings.redis_url),
        *check_docker_compose(repo_root),
    ]
    await message.answer("Диагностика\n" + format_checks(checks))


@router.message(Command("admin_doctor"))
async def admin_doctor(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    settings = get_settings()
    repo_root = repo_root_from_cwd()
    memory = ObsidianMemory(settings.obsidian_vault_path)
    user_id = message.from_user.id if message.from_user else 0
    indexed_count = memory.rebuild_user_index(user_id=user_id)
    access = AccessControlStore(settings.obsidian_vault_path)
    checks = [
        check_vault(settings.obsidian_vault_path),
        check_memory_index(settings.obsidian_vault_path),
        check_access_control(settings.obsidian_vault_path, settings.assistant_access_mode),
        *security_audit_checks(settings=settings, repo_root=repo_root),
        await _db_check(),
        await _redis_check(settings.redis_url),
        *check_docker_compose(repo_root),
    ]
    lines = [
        "Doctor",
        format_health_score(checks),
        format_checks(checks),
        f"Access mode: {settings.assistant_access_mode}",
        f"Context visibility: {settings.assistant_context_visibility}",
        f"Group trigger policy: {settings.assistant_group_trigger_policy}",
        f"Pending pairings: {len(access.list_pairing_codes())}",
        f"Allowed users: {len(access.allowed_users())}",
        f"Active space: {memory.get_active_space(user_id)}",
        f"Indexed user notes: {indexed_count}",
    ]
    await message.answer("\n".join(lines)[:3900])


@router.message(Command("pairing_approve"))
async def pairing_approve(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    code = (message.text or "").partition(" ")[2].strip()
    if not code:
        await message.answer("Использование: /pairing_approve <code>")
        return
    user_id = AccessControlStore(get_settings().obsidian_vault_path).approve_pairing_code(code=code)
    if user_id is None:
        await message.answer("Код не найден или истек.")
        return
    await message.answer(f"Пользователь {user_id} добавлен в allowlist.")


    AuditLogStore(get_settings().obsidian_vault_path).record(
        user_id=message.from_user.id if message.from_user else 0,
        action="pairing_approve",
        detail=str(user_id),
    )


@router.message(Command("access_list"))
async def access_list(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    users = sorted(AccessControlStore(get_settings().obsidian_vault_path).allowed_users())
    if not users:
        await message.answer("Allowlist пуст.")
        return
    await message.answer("Allowlist:\n" + "\n".join(f"- {user_id}" for user_id in users))


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


@router.message(Command("admin_secret_scan"))
async def admin_secret_scan(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    settings = get_settings()
    findings = scan_for_secrets(repo_root_from_cwd(), settings.obsidian_vault_path)
    AuditLogStore(settings.obsidian_vault_path).record(
        user_id=message.from_user.id if message.from_user else 0,
        action="admin_secret_scan",
        detail=f"findings={len(findings)}",
    )
    await message.answer(format_secret_findings(findings)[:3900])


@router.message(Command("admin_audit"))
async def admin_audit(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    events = AuditLogStore(get_settings().obsidian_vault_path).list_events()
    if not events:
        await message.answer("Audit log пуст.")
        return
    lines = ["Audit log:"]
    for event in events:
        lines.append(
            f"- {event.created_at:%Y-%m-%d %H:%M} "
            f"u{event.user_id} {event.action}: {event.detail}"
        )
    await message.answer("\n".join(lines)[:3900])


@router.message(Command("admin_onboarding"))
async def admin_onboarding(message: Message) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None):
        return
    settings = get_settings()
    lines = [
        "Admin onboarding",
        "1. Set ADMIN_TELEGRAM_IDS to your Telegram ID.",
        "2. Keep ASSISTANT_ACCESS_MODE=pairing.",
        "3. Run /admin_doctor and fix FAIL items.",
        "4. Ask a new user to message the bot and send you the pairing code.",
        "5. Approve with /pairing_approve <code>.",
        "6. Check /skills, /orders, /jobs, /agenda.",
        f"7. Mini App URL: {settings.tg_mini_app_url or 'not set'}",
    ]
    await message.answer("\n".join(lines))


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
