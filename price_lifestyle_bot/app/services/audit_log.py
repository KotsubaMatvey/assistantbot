from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class AuditEvent:
    id: str
    user_id: int
    action: str
    detail: str
    created_at: datetime


class AuditLogStore:
    def __init__(self, vault_path: str) -> None:
        self.path = Path(vault_path).expanduser() / "security" / "audit-log.jsonl"

    def record(
        self,
        *,
        user_id: int,
        action: str,
        detail: str = "",
        now: datetime | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=secrets.token_hex(4),
            user_id=user_id,
            action=action.strip(),
            detail=detail.strip()[:500],
            created_at=(now or datetime.now(UTC)).astimezone(UTC),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(_event_to_dict(event), ensure_ascii=False) + "\n")
        return event

    def list_events(self, *, user_id: int | None = None, limit: int = 20) -> list[AuditEvent]:
        if not self.path.exists():
            return []
        events = []
        for line in self.path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                events.append(_event_from_dict(json.loads(line)))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        if user_id is not None:
            events = [event for event in events if event.user_id == user_id]
        events.sort(key=lambda event: event.created_at, reverse=True)
        return events[:limit]


def _event_to_dict(event: AuditEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "user_id": event.user_id,
        "action": event.action,
        "detail": event.detail,
        "created_at": event.created_at.isoformat(),
    }


def _event_from_dict(raw: dict[str, object]) -> AuditEvent:
    return AuditEvent(
        id=str(raw["id"]),
        user_id=int(str(raw["user_id"])),
        action=str(raw["action"]),
        detail=str(raw.get("detail", "")),
        created_at=datetime.fromisoformat(str(raw["created_at"])).astimezone(UTC),
    )
