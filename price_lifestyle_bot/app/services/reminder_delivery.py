from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReminderDelivery:
    user_id: int
    reminder_id: str
    status: str
    attempts: int
    next_attempt_at: datetime | None
    lease_expires_at: datetime | None
    last_error: str


class ReminderDeliveryStore:
    def __init__(self, vault_path: str) -> None:
        root = Path(vault_path).expanduser() / ".assistantbot"
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "reminder-delivery.sqlite3"
        self._prepare()

    def claim(
        self,
        *,
        user_id: int,
        reminder_id: str,
        now: datetime | None = None,
        lease_seconds: int = 300,
    ) -> bool:
        current = _utc(now)
        lease_expires_at = current + timedelta(seconds=lease_seconds)
        with self._connect() as connection:
            connection.execute("begin immediate")
            delivery = self._get(connection, user_id=user_id, reminder_id=reminder_id)
            if delivery is None:
                connection.execute(
                    """
                    insert into reminder_deliveries (
                        user_id, reminder_id, status, attempts, next_attempt_at,
                        lease_expires_at, last_error, updated_at
                    ) values (?, ?, 'sending', 1, null, ?, '', ?)
                    """,
                    (user_id, reminder_id, lease_expires_at.isoformat(), current.isoformat()),
                )
                return True
            if delivery.status in {"sent", "uncertain"}:
                return False
            if delivery.status == "sending":
                if delivery.lease_expires_at is None or delivery.lease_expires_at > current:
                    return False
                connection.execute(
                    """
                    update reminder_deliveries
                    set status = 'uncertain', lease_expires_at = null,
                        last_error = ?, updated_at = ?
                    where user_id = ? and reminder_id = ?
                    """,
                    (
                        "Delivery interrupted while sending; manual review required.",
                        current.isoformat(),
                        user_id,
                        reminder_id,
                    ),
                )
                return False
            if delivery.next_attempt_at is not None and delivery.next_attempt_at > current:
                return False
            connection.execute(
                """
                update reminder_deliveries
                set status = 'sending', attempts = attempts + 1, next_attempt_at = null,
                    lease_expires_at = ?, last_error = '', updated_at = ?
                where user_id = ? and reminder_id = ?
                """,
                (lease_expires_at.isoformat(), current.isoformat(), user_id, reminder_id),
            )
            return True

    def mark_sent(
        self, *, user_id: int, reminder_id: str, now: datetime | None = None
    ) -> None:
        current = _utc(now)
        with self._connect() as connection:
            connection.execute(
                """
                update reminder_deliveries
                set status = 'sent', next_attempt_at = null, lease_expires_at = null,
                    last_error = '', updated_at = ?
                where user_id = ? and reminder_id = ?
                """,
                (current.isoformat(), user_id, reminder_id),
            )

    def mark_failed(
        self,
        *,
        user_id: int,
        reminder_id: str,
        error: str,
        now: datetime | None = None,
    ) -> None:
        current = _utc(now)
        with self._connect() as connection:
            delivery = self._get(connection, user_id=user_id, reminder_id=reminder_id)
            attempts = delivery.attempts if delivery is not None else 1
            delay_seconds = min(3600, 30 * (2 ** max(attempts - 1, 0)))
            connection.execute(
                """
                update reminder_deliveries
                set status = 'failed', next_attempt_at = ?, lease_expires_at = null,
                    last_error = ?, updated_at = ?
                where user_id = ? and reminder_id = ?
                """,
                (
                    (current + timedelta(seconds=delay_seconds)).isoformat(),
                    error[:500],
                    current.isoformat(),
                    user_id,
                    reminder_id,
                ),
            )

    def get(self, *, user_id: int, reminder_id: str) -> ReminderDelivery | None:
        with self._connect() as connection:
            return self._get(connection, user_id=user_id, reminder_id=reminder_id)

    def attention_required(self) -> list[ReminderDelivery]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                select user_id, reminder_id, status, attempts, next_attempt_at,
                       lease_expires_at, last_error
                from reminder_deliveries
                where status in ('failed', 'uncertain')
                order by updated_at desc
                """
            ).fetchall()
        return [_from_row(row) for row in rows]

    def _prepare(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists reminder_deliveries (
                    user_id integer not null,
                    reminder_id text not null,
                    status text not null,
                    attempts integer not null,
                    next_attempt_at text,
                    lease_expires_at text,
                    last_error text not null,
                    updated_at text not null,
                    primary key (user_id, reminder_id)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _get(
        self, connection: sqlite3.Connection, *, user_id: int, reminder_id: str
    ) -> ReminderDelivery | None:
        row = connection.execute(
            """
            select user_id, reminder_id, status, attempts, next_attempt_at,
                   lease_expires_at, last_error
            from reminder_deliveries
            where user_id = ? and reminder_id = ?
            """,
            (user_id, reminder_id),
        ).fetchone()
        return None if row is None else _from_row(row)


def _from_row(row: tuple[Any, ...]) -> ReminderDelivery:
    return ReminderDelivery(
        user_id=int(row[0]),
        reminder_id=str(row[1]),
        status=str(row[2]),
        attempts=int(row[3]),
        next_attempt_at=_parse_datetime(row[4]),
        lease_expires_at=_parse_datetime(row[5]),
        last_error=str(row[6]),
    )


def _parse_datetime(raw: object) -> datetime | None:
    if not raw:
        return None
    return datetime.fromisoformat(str(raw)).astimezone(UTC)


def _utc(value: datetime | None) -> datetime:
    return (value or datetime.now(UTC)).astimezone(UTC)
