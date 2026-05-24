from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from app.services import scheduler
from app.services.audit_log import AuditLogStore
from app.services.obsidian_memory import ObsidianMemory
from app.services.reminder_delivery import ReminderDeliveryStore


def test_scheduler_registers_opt_in_automatic_backup(monkeypatch) -> None:
    monkeypatch.setattr(
        scheduler,
        "get_settings",
        lambda: SimpleNamespace(
            scrape_interval_hours=12,
            admin_backup_enabled=True,
            admin_backup_interval_hours=24,
            admin_telegram_ids=[123],
        ),
    )

    scheduled = scheduler.create_scheduler(bot=object())  # type: ignore[arg-type]

    assert scheduled.get_job("send_admin_backup") is not None


def test_reminder_delivery_retries_failed_send_and_persists_sent_state(tmp_path) -> None:
    current = datetime(2026, 5, 24, 10, 0, tzinfo=UTC)
    store = ReminderDeliveryStore(str(tmp_path))

    assert store.claim(user_id=123, reminder_id="reminder", now=current) is True
    store.mark_failed(user_id=123, reminder_id="reminder", error="offline", now=current)
    assert (
        store.claim(user_id=123, reminder_id="reminder", now=current + timedelta(seconds=29))
        is False
    )
    assert (
        store.claim(user_id=123, reminder_id="reminder", now=current + timedelta(seconds=30))
        is True
    )
    store.mark_sent(user_id=123, reminder_id="reminder", now=current + timedelta(seconds=31))

    saved = ReminderDeliveryStore(str(tmp_path)).get(user_id=123, reminder_id="reminder")
    assert saved is not None
    assert saved.status == "sent"
    assert saved.attempts == 2


def test_reminder_delivery_marks_interrupted_inflight_delivery_uncertain(tmp_path) -> None:
    current = datetime(2026, 5, 24, 10, 0, tzinfo=UTC)
    store = ReminderDeliveryStore(str(tmp_path))

    assert (
        store.claim(user_id=123, reminder_id="reminder", now=current, lease_seconds=10) is True
    )
    assert (
        store.claim(user_id=123, reminder_id="reminder", now=current + timedelta(seconds=11))
        is False
    )

    saved = store.get(user_id=123, reminder_id="reminder")
    assert saved is not None
    assert saved.status == "uncertain"
    assert store.attention_required() == [saved]


@pytest.mark.asyncio
async def test_scheduler_sends_reminder_once_and_records_delivery(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        scheduler,
        "get_settings",
        lambda: SimpleNamespace(obsidian_vault_path=str(tmp_path)),
    )
    memory = ObsidianMemory(str(tmp_path))
    reminder_path = memory.create_reminder(
        user_id=123,
        text="call bank",
        due_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
    )

    class FakeBot:
        def __init__(self) -> None:
            self.messages: list[tuple[int, str]] = []

        async def send_message(self, user_id: int, text: str) -> None:
            self.messages.append((user_id, text))

    bot = FakeBot()
    await scheduler._send_due_reminders(bot)  # type: ignore[arg-type]
    await scheduler._send_due_reminders(bot)  # type: ignore[arg-type]

    delivery = ReminderDeliveryStore(str(tmp_path)).get(
        user_id=123, reminder_id=reminder_path.stem
    )
    assert bot.messages == [(123, "Напоминание:\ncall bank")]
    assert delivery is not None
    assert delivery.status == "sent"
    assert memory.list_reminders(user_id=123) == []
    assert AuditLogStore(str(tmp_path)).list_events(user_id=123)[0].action == "reminder_delivered"
