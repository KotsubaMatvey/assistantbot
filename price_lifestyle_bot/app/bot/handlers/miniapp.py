from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from app.bot.handlers.lifestyle import (
    accounts_handler,
    assistants_handler,
    budget_handler,
    budget_plan_handler,
    cashflow_handler,
    check_alerts_handler,
    evening_handler,
    expense_handler,
    income_handler,
    morning_handler,
    pantry_deals_handler,
    pantry_handler,
    pantry_plan_handler,
    price_alerts_handler,
    subscriptions_handler,
    week_handler,
)
from app.bot.handlers.markets import market_brief_command, markets_command
from app.bot.handlers.memory import (
    agenda_handler,
    assistant_capabilities_handler,
    capability_center_handler,
    compact_handler,
    lifestyle_context_handler,
    memory_profile_handler,
    memory_tree_handler,
    new_session_handler,
    objects_handler,
    people_handler,
    recent_handler,
    skills_handler,
    source_list_handler,
    source_sync_handler,
    sources_handler,
    status_handler,
    tasks_handler,
    today_handler,
    tools_handler,
    weekly_summary_handler,
)
from app.bot.handlers.shopping import _handle_basket
from app.config import get_settings
from app.logging_config import get_logger
from app.services.audit_log import AuditLogStore
from app.services.mini_app import parse_mini_app_payload
from app.services.mini_app_state import (
    add_mini_app_note,
    add_mini_app_person,
    add_mini_app_receipt,
    add_mini_app_reminder,
    add_mini_app_task,
    add_mini_app_transaction,
    update_mini_app_account,
    update_mini_app_subscription,
)

router = Router()
logger = get_logger(__name__)


@router.message(F.web_app_data)
async def mini_app_data_handler(message: Message) -> None:
    raw_data = message.web_app_data.data if message.web_app_data else ""
    settings = get_settings()
    user_id = message.from_user.id if message.from_user else 0
    try:
        payload = parse_mini_app_payload(raw_data)
    except ValueError as exc:
        _audit_mini_app(message, "mini_app_rejected", str(exc))
        await message.answer(f"Mini App payload не обработан: {exc}")
        return

    if payload.type == "basket_compare":
        _audit_mini_app(
            message,
            "mini_app_basket_compare",
            f"chars={len(payload.text)} lines={len(payload.text.splitlines())}",
        )
        await _handle_basket(message, payload.text)
        return
    if payload.type == "assistant_message":
        _audit_mini_app(
            message,
            "mini_app_assistant_message",
            f"chars={len(payload.text)}",
        )
        await message.answer(_pixel_assistant_reply(payload.text))
        return
    if payload.type == "task_create":
        add_mini_app_task(
            vault_path=settings.obsidian_vault_path,
            user_id=user_id,
            text=payload.text,
        )
        _audit_mini_app(message, "mini_app_task_create", payload.text)
        await message.answer("Task saved from Mini App.")
        return
    if payload.type == "note_create":
        add_mini_app_note(
            vault_path=settings.obsidian_vault_path,
            user_id=user_id,
            text=payload.text,
        )
        _audit_mini_app(message, "mini_app_note_create", payload.text)
        await message.answer("Note saved from Mini App.")
        return
    if payload.type == "reminder_create":
        try:
            add_mini_app_reminder(
                vault_path=settings.obsidian_vault_path,
                user_id=user_id,
                text=payload.text,
                timezone_name=settings.timezone,
            )
        except ValueError as exc:
            _audit_mini_app(message, "mini_app_reminder_rejected", str(exc))
            await message.answer(f"Reminder rejected: {exc}")
            return
        _audit_mini_app(message, "mini_app_reminder_create", payload.text)
        await message.answer("Reminder saved from Mini App.")
        return
    if payload.type == "person_note":
        try:
            add_mini_app_person(
                vault_path=settings.obsidian_vault_path,
                user_id=user_id,
                name=payload.data["name"],
                note=payload.data["note"],
            )
        except ValueError as exc:
            _audit_mini_app(message, "mini_app_person_rejected", str(exc))
            await message.answer(f"Person note rejected: {exc}")
            return
        _audit_mini_app(message, "mini_app_person_note", payload.data["name"])
        await message.answer("Person note saved from Mini App.")
        return
    if payload.type == "finance_transaction":
        try:
            add_mini_app_transaction(
                vault_path=settings.obsidian_vault_path,
                user_id=user_id,
                kind=payload.data["kind"],
                amount=payload.data["amount"],
                category=payload.data["category"],
                note=payload.data.get("note", ""),
            )
        except ValueError as exc:
            _audit_mini_app(message, "mini_app_finance_rejected", str(exc))
            await message.answer(f"Finance transaction rejected: {exc}")
            return
        _audit_mini_app(
            message,
            "mini_app_finance_transaction",
            f"{payload.data['kind']} {payload.data['amount']} {payload.data['category']}",
        )
        await message.answer("Finance transaction saved from Mini App.")
        return
    if payload.type == "finance_account":
        try:
            update_mini_app_account(
                vault_path=settings.obsidian_vault_path,
                user_id=user_id,
                name=payload.data["name"],
                balance=payload.data["balance"],
            )
        except ValueError as exc:
            _audit_mini_app(message, "mini_app_account_rejected", str(exc))
            await message.answer(f"Account rejected: {exc}")
            return
        _audit_mini_app(message, "mini_app_account_update", payload.data["name"])
        await message.answer("Account saved from Mini App.")
        return
    if payload.type == "finance_subscription":
        try:
            update_mini_app_subscription(
                vault_path=settings.obsidian_vault_path,
                user_id=user_id,
                name=payload.data["name"],
                amount=payload.data["amount"],
            )
        except ValueError as exc:
            _audit_mini_app(message, "mini_app_subscription_rejected", str(exc))
            await message.answer(f"Subscription rejected: {exc}")
            return
        _audit_mini_app(message, "mini_app_subscription_update", payload.data["name"])
        await message.answer("Subscription saved from Mini App.")
        return
    if payload.type == "receipt_save":
        try:
            add_mini_app_receipt(
                vault_path=settings.obsidian_vault_path,
                user_id=user_id,
                text=payload.text,
            )
        except ValueError as exc:
            _audit_mini_app(message, "mini_app_receipt_rejected", str(exc))
            await message.answer(f"Receipt rejected: {exc}")
            return
        _audit_mini_app(message, "mini_app_receipt_save", f"chars={len(payload.text)}")
        await message.answer("Receipt saved from Mini App.")
        return

    _audit_mini_app(message, "mini_app_command", payload.command)
    if payload.command == "markets":
        await markets_command(message)
    elif payload.command == "market_brief":
        await market_brief_command(message)
    elif payload.command == "status":
        await status_handler(message)
    elif payload.command == "capability_center":
        await capability_center_handler(message)
    elif payload.command == "agenda":
        await agenda_handler(message)
    elif payload.command == "lifestyle_context":
        await lifestyle_context_handler(message)
    elif payload.command == "compact":
        await compact_handler(message)
    elif payload.command == "new":
        await new_session_handler(message)
    elif payload.command == "morning":
        await morning_handler(message)
    elif payload.command == "evening":
        await evening_handler(message)
    elif payload.command == "week":
        await week_handler(message)
    elif payload.command == "price_alerts":
        await price_alerts_handler(message)
    elif payload.command == "check_alerts":
        await check_alerts_handler(message)
    elif payload.command == "pantry":
        await pantry_handler(message)
    elif payload.command == "pantry_plan":
        await pantry_plan_handler(message)
    elif payload.command == "pantry_deals":
        await pantry_deals_handler(message)
    elif payload.command == "budget":
        await budget_handler(message)
    elif payload.command == "budget_plan":
        await budget_plan_handler(message)
    elif payload.command == "expense":
        await expense_handler(message)
    elif payload.command == "income":
        await income_handler(message)
    elif payload.command == "accounts":
        await accounts_handler(message)
    elif payload.command == "subscriptions":
        await subscriptions_handler(message)
    elif payload.command == "cashflow":
        await cashflow_handler(message)
    elif payload.command == "assistants":
        await assistants_handler(message)
    elif payload.command == "today":
        await today_handler(message)
    elif payload.command == "tasks":
        await tasks_handler(message)
    elif payload.command == "people":
        await people_handler(message)
    elif payload.command == "objects":
        await objects_handler(message)
    elif payload.command == "recent":
        await recent_handler(message)
    elif payload.command == "sources":
        await sources_handler(message)
    elif payload.command == "source_list":
        await source_list_handler(message)
    elif payload.command == "source_sync":
        await source_sync_handler(message)
    elif payload.command == "memory_tree":
        await memory_tree_handler(message)
    elif payload.command == "memory_profile":
        await memory_profile_handler(message)
    elif payload.command == "weekly_summary":
        await weekly_summary_handler(message)
    elif payload.command == "tools":
        await tools_handler(message)
    elif payload.command == "skills":
        await skills_handler(message)
    elif payload.command == "assistant_capabilities":
        await assistant_capabilities_handler(message)


def _audit_mini_app(message: Message, action: str, detail: str) -> None:
    user_id = message.from_user.id if message.from_user else 0
    try:
        AuditLogStore(get_settings().obsidian_vault_path).record(
            user_id=user_id,
            action=action,
            detail=detail,
        )
    except Exception as exc:
        logger.warning("mini_app_audit_failed", action=action, error=str(exc))


def _pixel_assistant_reply(text: str) -> str:
    normalized = text.lower()
    if "цен" in normalized or "покуп" in normalized:
        return "Pixel helper: для покупок используй /prices, /watch_price и /pantry_plan."
    if "рын" in normalized or "btc" in normalized:
        return "Pixel helper: для рынка используй /markets, /market_brief или /morning."
    if "зада" in normalized or "план" in normalized:
        return "Pixel helper: для задач используй /agenda, /task и /compact."
    if "пам" in normalized or "контекст" in normalized:
        return "Pixel helper: для контекста используй /lifestyle_context или /memory."
    return (
        "Pixel helper: могу открыть /morning, /agenda, /markets, /market_brief, "
        "/pantry, /budget или /lifestyle_context."
    )
