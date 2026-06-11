from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.services.agenda import build_agenda
from app.services.assistant_jobs import AssistantJobStore
from app.services.audit_log import AuditLogStore
from app.services.finance import FinanceStore, parse_amount
from app.services.memory_tree import MemoryTreeStore
from app.services.object_store import ObjectStore
from app.services.obsidian_memory import ObsidianMemory, parse_reminder_request
from app.services.source_connectors import SourceRecord, SourceStore
from app.services.spending import SpendingStore, current_month, parse_receipt_text


def build_mini_app_state(
    *,
    vault_path: str,
    user_id: int,
    timezone_name: str,
) -> dict[str, Any]:
    timezone = ZoneInfo(timezone_name)
    memory = ObsidianMemory(vault_path)
    objects = ObjectStore(vault_path)
    objects.index_recent_notes(user_id=user_id, memory=memory)
    spending = SpendingStore(vault_path)
    finance = FinanceStore(vault_path)
    month = current_month()
    budget = spending.budget_summary(user_id=user_id, month=month)
    cashflow = finance.cashflow_summary(
        user_id=user_id,
        month=month,
        receipt_expenses=budget.spent,
    )
    tasks = memory.list_open_tasks(user_id=user_id, limit=20)
    reminders = memory.list_reminders(user_id=user_id, limit=20)
    recent_notes = memory.recent_notes(user_id=user_id, limit=20)
    object_stats = objects.stats(user_id=user_id)
    sources = SourceStore(vault_path).list_sources(user_id=user_id)
    health = MemoryTreeStore(vault_path).health(memory=memory, user_id=user_id)
    events = [
        event
        for event in AuditLogStore(vault_path).list_events(limit=100)
        if event.user_id == user_id and event.action.startswith("mini_app_")
    ][:12]
    agenda = build_agenda(
        memory=memory,
        jobs=AssistantJobStore(vault_path, timezone_name=timezone_name),
        user_id=user_id,
        timezone_name=timezone_name,
    )
    return {
        "user": {"id": user_id},
        "today": {
            "agenda": agenda,
            "digest": memory.today_digest(user_id=user_id),
            "tasks": [
                {"id": task.id, "snippet": task.snippet, "tags": task.tags}
                for task in tasks
            ],
            "reminders": [
                {
                    "id": reminder.id,
                    "snippet": reminder.snippet,
                    "due_at": reminder.due_at.astimezone(timezone).isoformat(),
                }
                for reminder in reminders
            ],
            "notes": [
                {
                    "id": note.path.stem,
                    "snippet": note.snippet,
                    "type": note.note_type,
                    "tags": note.tags,
                }
                for note in recent_notes
            ],
            "focus": _focus_items(tasks, reminders, timezone),
        },
        "finance": {
            "month": month,
            "balance": _money(cashflow.balance),
            "income": _money(cashflow.income),
            "expenses": _money(cashflow.expenses + cashflow.receipt_expenses),
            "subscriptions_total": _money(cashflow.subscriptions),
            "forecast": _money(cashflow.forecast),
            "budget": {
                "limit": _money(budget.budget),
                "spent": _money(budget.spent),
                "remaining": _money(budget.remaining),
                "projected": _money(budget.projected_spend),
                "receipts_count": budget.receipts_count,
                "categories": [
                    {"name": name, "amount": _money(amount)}
                    for name, amount in budget.category_totals[:8]
                ],
            },
            "accounts": [
                {
                    "id": account.id,
                    "name": account.name,
                    "balance": _money(account.balance),
                    "currency": account.currency,
                }
                for account in finance.list_accounts(user_id=user_id)
            ],
            "transactions": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "amount": _money(item.amount),
                    "category": item.category,
                    "note": item.note,
                    "created_at": item.created_at.astimezone(timezone).isoformat(),
                }
                for item in finance.list_transactions(user_id=user_id, limit=20)
            ],
            "subscriptions": [
                {
                    "id": item.id,
                    "name": item.name,
                    "amount": _money(item.amount),
                    "cycle": item.cycle,
                }
                for item in finance.list_subscriptions(user_id=user_id)
            ],
            "receipts": [
                {
                    "id": receipt.id,
                    "store": receipt.store,
                    "total": _money(receipt.total),
                    "purchased_at": receipt.purchased_at.astimezone(timezone).isoformat(),
                    "items_count": len(receipt.items),
                }
                for receipt in spending.list_receipts(user_id=user_id, limit=20)
            ],
        },
        "memory": {
            "health": {
                "raw_captures": health.raw_captures,
                "daily_summaries": health.daily_summaries,
                "project_summaries": health.project_summaries,
                "profile_exists": health.profile_exists,
                "weekly_exists": health.weekly_exists,
                "latest_raw": health.latest_raw,
                "latest_summary": health.latest_summary,
            },
            "objects": {
                "total": object_stats.total,
                "by_type": [
                    {"type": object_type, "count": count}
                    for object_type, count in object_stats.by_type
                ],
                "recent": [
                    {
                        "id": item.id,
                        "type": item.type,
                        "title": item.title,
                        "tags": item.tags,
                    }
                    for item in objects.list_objects(user_id=user_id, limit=20)
                ],
            },
            "sources": [
                {
                    "id": source.id,
                    "type": source.type,
                    "url": source.url,
                    "enabled": source.enabled,
                    "last_sync_at": _datetime_or_empty(source.last_sync_at),
                    "last_error": source.last_error,
                }
                for source in sources
            ],
            "events": [
                {
                    "id": event.id,
                    "action": event.action,
                    "detail": event.detail,
                    "created_at": event.created_at.astimezone(timezone).isoformat(),
                }
                for event in events
            ],
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }


def add_mini_app_transaction(
    *,
    vault_path: str,
    user_id: int,
    kind: str,
    amount: str,
    category: str,
    note: str = "",
) -> None:
    FinanceStore(vault_path).add_transaction(
        user_id=user_id,
        kind=kind,
        amount=parse_amount(amount),
        category=category,
        note=note,
    )


def update_mini_app_account(
    *,
    vault_path: str,
    user_id: int,
    name: str,
    balance: str,
) -> None:
    FinanceStore(vault_path).upsert_account(
        user_id=user_id,
        name=name,
        balance=parse_amount(balance),
    )


def update_mini_app_subscription(
    *,
    vault_path: str,
    user_id: int,
    name: str,
    amount: str,
) -> None:
    FinanceStore(vault_path).upsert_subscription(
        user_id=user_id,
        name=name,
        amount=parse_amount(amount),
    )


def add_mini_app_task(*, vault_path: str, user_id: int, text: str) -> None:
    ObsidianMemory(vault_path).create_task(user_id=user_id, text=text)


def complete_mini_app_task(*, vault_path: str, user_id: int, task_id: str) -> bool:
    clean_id = task_id.strip()
    if not clean_id or any(part in clean_id for part in ("/", "\\", "..")):
        raise ValueError("task id is invalid")
    return ObsidianMemory(vault_path).complete_task(user_id=user_id, task_id=clean_id)


def add_mini_app_note(*, vault_path: str, user_id: int, text: str) -> None:
    ObsidianMemory(vault_path).remember_user_note(user_id=user_id, text=text)


def add_mini_app_reminder(
    *,
    vault_path: str,
    user_id: int,
    text: str,
    timezone_name: str,
) -> None:
    due_at, body = parse_reminder_request(text, timezone_name=timezone_name)
    ObsidianMemory(vault_path).create_reminder(user_id=user_id, text=body, due_at=due_at)


def add_mini_app_person(
    *,
    vault_path: str,
    user_id: int,
    name: str,
    note: str,
) -> None:
    ObsidianMemory(vault_path).remember_person_note(
        user_id=user_id,
        person_name=name,
        text=note,
    )


def add_mini_app_receipt(*, vault_path: str, user_id: int, text: str) -> None:
    store, items = parse_receipt_text(text)
    receipt = SpendingStore(vault_path).add_receipt(user_id=user_id, store=store, items=items)
    ObjectStore(vault_path).index_receipt(
        user_id=user_id,
        receipt_id=receipt.id,
        store=receipt.store,
        total=str(receipt.total),
        items=[(item.name, str(item.price), item.category) for item in receipt.items],
        purchased_at=receipt.purchased_at,
    )


def add_mini_app_source(
    *,
    vault_path: str,
    user_id: int,
    source_type: str,
    target: str,
) -> SourceRecord:
    return SourceStore(vault_path).add_source(
        user_id=user_id,
        source_type=source_type,
        target=target,
    )


def delete_mini_app_source(*, vault_path: str, user_id: int, source_id: str) -> bool:
    clean_id = source_id.strip()
    if not clean_id:
        raise ValueError("source id is empty")
    return SourceStore(vault_path).delete_source(user_id=user_id, source_id=clean_id)


def _focus_items(
    tasks: list[Any],
    reminders: list[Any],
    timezone: ZoneInfo,
) -> list[dict[str, str]]:
    items = [
        {"type": "task", "title": task.snippet, "detail": task.id}
        for task in tasks[:3]
    ]
    items.extend(
        {
            "type": "reminder",
            "title": reminder.snippet,
            "detail": reminder.due_at.astimezone(timezone).strftime("%Y-%m-%d %H:%M"),
        }
        for reminder in reminders[:3]
    )
    return items[:5]


def _money(value: Decimal | None) -> str:
    if value is None:
        return ""
    return str(value.quantize(Decimal("0.01")))


def _datetime_or_empty(value: datetime | None) -> str:
    return value.isoformat() if value else ""
