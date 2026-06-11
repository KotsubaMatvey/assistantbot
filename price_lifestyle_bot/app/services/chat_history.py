from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.services.file_io import atomic_write_text

MAX_HISTORY_TURNS = 12
MAX_TURN_CHARS = 1500


@dataclass(frozen=True)
class ChatTurn:
    role: str
    text: str
    at: datetime


class ChatHistoryStore:
    """Rolling freeform-conversation history used as context for the LLM chat."""

    def __init__(self, vault_path: str, *, max_turns: int = MAX_HISTORY_TURNS) -> None:
        self.vault_path = Path(vault_path).expanduser()
        self.max_turns = max_turns

    def list_turns(self, *, user_id: int) -> list[ChatTurn]:
        path = self._path(user_id)
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(raw, list):
            return []
        turns: list[ChatTurn] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                turns.append(
                    ChatTurn(
                        role=str(item["role"]),
                        text=str(item["text"]),
                        at=datetime.fromisoformat(str(item["at"])).astimezone(UTC),
                    )
                )
            except (KeyError, ValueError):
                continue
        return turns[-self.max_turns :]

    def append_exchange(
        self,
        *,
        user_id: int,
        user_text: str,
        assistant_text: str,
        now: datetime | None = None,
    ) -> None:
        at = (now or datetime.now(UTC)).astimezone(UTC)
        turns = [
            *self.list_turns(user_id=user_id),
            ChatTurn(role="user", text=user_text[:MAX_TURN_CHARS], at=at),
            ChatTurn(role="assistant", text=assistant_text[:MAX_TURN_CHARS], at=at),
        ]
        self._write(user_id=user_id, turns=turns[-self.max_turns :])

    def clear(self, *, user_id: int) -> None:
        path = self._path(user_id)
        if path.exists():
            self._write(user_id=user_id, turns=[])

    def _write(self, *, user_id: int, turns: list[ChatTurn]) -> None:
        atomic_write_text(
            self._path(user_id),
            json.dumps(
                [
                    {"role": turn.role, "text": turn.text, "at": turn.at.isoformat()}
                    for turn in turns
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )

    def _path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "dialogue" / "chat-history.json"
