from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class PendingAction:
    id: str
    user_id: int
    action: str
    payload: dict[str, str]
    created_at: datetime
    expires_at: datetime


class ActionApprovalStore:
    def __init__(self, vault_path: str) -> None:
        self.path = Path(vault_path).expanduser() / "security" / "pending-actions.json"

    def create(
        self,
        *,
        user_id: int,
        action: str,
        payload: dict[str, str],
        ttl_minutes: int = 30,
        now: datetime | None = None,
    ) -> PendingAction:
        current = now or datetime.now(UTC)
        pending = PendingAction(
            id=secrets.token_hex(3),
            user_id=user_id,
            action=action,
            payload=payload,
            created_at=current,
            expires_at=current + timedelta(minutes=ttl_minutes),
        )
        actions = [action for action in self.list_actions(now=current) if action.user_id != user_id]
        actions.append(pending)
        self._write(actions)
        return pending

    def consume(
        self,
        *,
        user_id: int,
        approval_id: str,
        now: datetime | None = None,
    ) -> PendingAction | None:
        current = now or datetime.now(UTC)
        actions = self.list_actions(now=current)
        found: PendingAction | None = None
        remaining: list[PendingAction] = []
        for action in actions:
            if action.user_id == user_id and action.id == approval_id:
                found = action
                continue
            remaining.append(action)
        self._write(remaining)
        return found

    def list_actions(
        self,
        *,
        user_id: int | None = None,
        now: datetime | None = None,
    ) -> list[PendingAction]:
        current = now or datetime.now(UTC)
        stored_actions = self._read()
        actions = [
            action
            for action in stored_actions
            if action.expires_at > current and (user_id is None or action.user_id == user_id)
        ]
        if len(actions) != len(stored_actions):
            self._write(actions)
        return actions

    def _read(self) -> list[PendingAction]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        actions: list[PendingAction] = []
        for item in raw:
            actions.append(
                PendingAction(
                    id=str(item["id"]),
                    user_id=int(item["user_id"]),
                    action=str(item["action"]),
                    payload={str(key): str(value) for key, value in item["payload"].items()},
                    created_at=datetime.fromisoformat(str(item["created_at"])).astimezone(UTC),
                    expires_at=datetime.fromisoformat(str(item["expires_at"])).astimezone(UTC),
                )
            )
        return actions

    def _write(self, actions: list[PendingAction]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                [
                    {
                        "id": action.id,
                        "user_id": action.user_id,
                        "action": action.action,
                        "payload": action.payload,
                        "created_at": action.created_at.isoformat(),
                        "expires_at": action.expires_at.isoformat(),
                    }
                    for action in actions
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
