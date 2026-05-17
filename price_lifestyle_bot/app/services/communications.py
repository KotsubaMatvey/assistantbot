from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class FollowUp:
    id: str
    user_id: int
    person: str
    text: str
    due_at: datetime
    reminder_id: str
    status: str
    created_at: datetime


class FollowUpStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def add_followup(
        self,
        *,
        user_id: int,
        person: str,
        text: str,
        due_at: datetime,
        reminder_id: str,
        created_at: datetime | None = None,
    ) -> FollowUp:
        clean_person = " ".join(person.strip().split())
        clean_text = text.strip()
        if not clean_person:
            raise ValueError("person is empty")
        if not clean_text:
            raise ValueError("follow-up text is empty")
        followup = FollowUp(
            id=secrets.token_hex(4),
            user_id=user_id,
            person=clean_person,
            text=clean_text,
            due_at=due_at.astimezone(UTC),
            reminder_id=reminder_id,
            status="open",
            created_at=(created_at or datetime.now(UTC)).astimezone(UTC),
        )
        items = self.list_followups(user_id=user_id, limit=10_000)
        items.append(followup)
        self._write_followups(user_id=user_id, followups=items[-10_000:])
        return followup

    def list_followups(self, *, user_id: int, limit: int = 20) -> list[FollowUp]:
        path = self._path(user_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        followups = [_followup_from_dict(item) for item in raw if isinstance(item, dict)]
        followups.sort(key=lambda item: item.due_at)
        return followups[:limit]

    def _write_followups(self, *, user_id: int, followups: list[FollowUp]) -> None:
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                [_followup_to_dict(item) for item in followups],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "communications" / "followups.json"


def parse_person_text(text: str) -> tuple[str, str]:
    person, _, body = text.strip().partition(" ")
    if not person or not body.strip():
        raise ValueError("usage: <person> <text>")
    return person, body.strip()


def draft_email(person: str, prompt: str) -> str:
    clean_person = " ".join(person.strip().split())
    clean_prompt = prompt.strip()
    if not clean_person or not clean_prompt:
        raise ValueError("person and prompt are required")
    return "\n".join(
        [
            f"To: {clean_person}",
            "Subject: ",
            "",
            f"Hi {clean_person},",
            "",
            clean_prompt,
            "",
            "Best,",
        ]
    )


def format_followups(followups: list[FollowUp]) -> str:
    if not followups:
        return "Follow-ups are empty."
    lines = ["Follow-ups:"]
    for item in followups:
        lines.append(
            f"- {item.due_at:%Y-%m-%d %H:%M} {item.person}: {item.text} ({item.reminder_id})"
        )
    return "\n".join(lines)


def _followup_to_dict(followup: FollowUp) -> dict[str, object]:
    return {
        "id": followup.id,
        "user_id": followup.user_id,
        "person": followup.person,
        "text": followup.text,
        "due_at": followup.due_at.isoformat(),
        "reminder_id": followup.reminder_id,
        "status": followup.status,
        "created_at": followup.created_at.isoformat(),
    }


def _followup_from_dict(raw: dict[str, object]) -> FollowUp:
    return FollowUp(
        id=str(raw["id"]),
        user_id=int(str(raw["user_id"])),
        person=str(raw["person"]),
        text=str(raw["text"]),
        due_at=datetime.fromisoformat(str(raw["due_at"])).astimezone(UTC),
        reminder_id=str(raw["reminder_id"]),
        status=str(raw.get("status", "open")),
        created_at=datetime.fromisoformat(str(raw["created_at"])).astimezone(UTC),
    )
