from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ASSISTANT_MODES = ("secretary", "researcher", "editor", "analyst")


@dataclass(frozen=True)
class AssistantRuntimeState:
    mode: str = "secretary"
    trace_enabled: bool = False
    verbose_enabled: bool = False
    session_epoch: int = 0
    updated_at: datetime | None = None


class AssistantRuntimeStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def get_state(self, *, user_id: int) -> AssistantRuntimeState:
        path = self._state_path(user_id)
        if not path.exists():
            return AssistantRuntimeState()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return AssistantRuntimeState(
            mode=str(raw.get("mode", "secretary")),
            trace_enabled=bool(raw.get("trace_enabled", False)),
            verbose_enabled=bool(raw.get("verbose_enabled", False)),
            session_epoch=int(raw.get("session_epoch", 0)),
            updated_at=_parse_datetime(str(raw.get("updated_at", ""))),
        )

    def set_mode(self, *, user_id: int, mode: str) -> AssistantRuntimeState:
        normalized = mode.strip().lower()
        if normalized not in ASSISTANT_MODES:
            raise ValueError(f"mode must be one of: {', '.join(ASSISTANT_MODES)}")
        state = self.get_state(user_id=user_id)
        updated = AssistantRuntimeState(
            mode=normalized,
            trace_enabled=state.trace_enabled,
            verbose_enabled=state.verbose_enabled,
            session_epoch=state.session_epoch,
            updated_at=datetime.now(UTC),
        )
        self._write_state(user_id=user_id, state=updated)
        return updated

    def set_trace(self, *, user_id: int, enabled: bool) -> AssistantRuntimeState:
        state = self.get_state(user_id=user_id)
        updated = AssistantRuntimeState(
            mode=state.mode,
            trace_enabled=enabled,
            verbose_enabled=state.verbose_enabled,
            session_epoch=state.session_epoch,
            updated_at=datetime.now(UTC),
        )
        self._write_state(user_id=user_id, state=updated)
        return updated

    def set_verbose(self, *, user_id: int, enabled: bool) -> AssistantRuntimeState:
        state = self.get_state(user_id=user_id)
        updated = AssistantRuntimeState(
            mode=state.mode,
            trace_enabled=state.trace_enabled,
            verbose_enabled=enabled,
            session_epoch=state.session_epoch,
            updated_at=datetime.now(UTC),
        )
        self._write_state(user_id=user_id, state=updated)
        return updated

    def reset_session(self, *, user_id: int) -> AssistantRuntimeState:
        state = self.get_state(user_id=user_id)
        updated = AssistantRuntimeState(
            mode=state.mode,
            trace_enabled=state.trace_enabled,
            verbose_enabled=state.verbose_enabled,
            session_epoch=state.session_epoch + 1,
            updated_at=datetime.now(UTC),
        )
        self._write_state(user_id=user_id, state=updated)
        return updated

    def _write_state(self, *, user_id: int, state: AssistantRuntimeState) -> None:
        path = self._state_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "mode": state.mode,
                    "trace_enabled": state.trace_enabled,
                    "verbose_enabled": state.verbose_enabled,
                    "session_epoch": state.session_epoch,
                    "updated_at": (state.updated_at or datetime.now(UTC)).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _state_path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "assistant-state.json"


def parse_on_off(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"on", "true", "1", "yes", "да", "вкл"}:
        return True
    if normalized in {"off", "false", "0", "no", "нет", "выкл"}:
        return False
    raise ValueError("expected on/off")


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
