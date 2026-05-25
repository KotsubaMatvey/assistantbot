from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.assistant_jobs import AssistantJobStore
from app.services.audit_log import AuditLogStore
from app.services.file_io import atomic_write_text
from app.services.finance import FinanceStore, format_money, parse_amount
from app.services.obsidian_memory import ObsidianMemory, parse_reminder_request
from app.services.spending import SpendingStore, format_receipt, parse_receipt_text


@dataclass(frozen=True)
class ChatButton:
    text: str
    data: str


@dataclass(frozen=True)
class ChatReply:
    text: str
    rows: tuple[tuple[ChatButton, ...], ...] = ()
    event: str | None = None


@dataclass(frozen=True)
class PendingDialogue:
    kind: str
    payload: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DialogueAction:
    id: str
    kind: str
    ref: str
    label: str
    payload: dict[str, str]
    created_at: datetime


@dataclass(frozen=True)
class DialogueProfile:
    concise: bool = False
    evening_hour: int = 19
    afternoon_hour: int = 14


@dataclass(frozen=True)
class DialogueState:
    pending: PendingDialogue | None = None
    actions: tuple[DialogueAction, ...] = ()
    profile: DialogueProfile = field(default_factory=DialogueProfile)


@dataclass(frozen=True)
class ShoppingItem:
    id: str
    text: str
    added_at: datetime


@dataclass(frozen=True)
class FactRevision:
    subject: str
    value: str
    updated_at: datetime


class ChatDialogueStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def state(self, *, user_id: int) -> DialogueState:
        path = self._state_path(user_id)
        if not path.exists():
            return DialogueState()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DialogueState()
        pending_raw = raw.get("pending")
        pending = None
        if isinstance(pending_raw, dict) and pending_raw.get("kind"):
            pending = PendingDialogue(
                kind=str(pending_raw["kind"]),
                payload={
                    str(key): str(value)
                    for key, value in dict(pending_raw.get("payload") or {}).items()
                },
            )
        profile_raw = raw.get("profile") if isinstance(raw.get("profile"), dict) else {}
        profile = DialogueProfile(
            concise=bool(profile_raw.get("concise", False)),
            evening_hour=_hour(profile_raw.get("evening_hour"), default=19),
            afternoon_hour=_hour(profile_raw.get("afternoon_hour"), default=14),
        )
        actions: list[DialogueAction] = []
        for item in raw.get("actions", []):
            if not isinstance(item, dict):
                continue
            try:
                actions.append(
                    DialogueAction(
                        id=str(item["id"]),
                        kind=str(item["kind"]),
                        ref=str(item.get("ref", "")),
                        label=str(item.get("label", "")),
                        payload={
                            str(key): str(value)
                            for key, value in dict(item.get("payload") or {}).items()
                        },
                        created_at=datetime.fromisoformat(str(item["created_at"])).astimezone(UTC),
                    )
                )
            except (KeyError, ValueError):
                continue
        return DialogueState(pending=pending, actions=tuple(actions[:20]), profile=profile)

    def write(self, *, user_id: int, state: DialogueState) -> None:
        path = self._state_path(user_id)
        atomic_write_text(
            path,
            json.dumps(
                {
                    "pending": (
                        {"kind": state.pending.kind, "payload": state.pending.payload}
                        if state.pending
                        else None
                    ),
                    "profile": {
                        "concise": state.profile.concise,
                        "evening_hour": state.profile.evening_hour,
                        "afternoon_hour": state.profile.afternoon_hour,
                    },
                    "actions": [
                        {
                            "id": action.id,
                            "kind": action.kind,
                            "ref": action.ref,
                            "label": action.label,
                            "payload": action.payload,
                            "created_at": action.created_at.isoformat(),
                        }
                        for action in state.actions[:20]
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

    def pending(self, *, user_id: int, kind: str, payload: dict[str, str]) -> None:
        state = self.state(user_id=user_id)
        self.write(user_id=user_id, state=replace(state, pending=PendingDialogue(kind, payload)))

    def clear_pending(self, *, user_id: int) -> None:
        state = self.state(user_id=user_id)
        self.write(user_id=user_id, state=replace(state, pending=None))

    def remember_action(
        self,
        *,
        user_id: int,
        kind: str,
        ref: str,
        label: str,
        payload: dict[str, str] | None = None,
        now: datetime | None = None,
    ) -> DialogueAction:
        state = self.state(user_id=user_id)
        action = DialogueAction(
            id=secrets.token_hex(3),
            kind=kind,
            ref=ref,
            label=label,
            payload=payload or {},
            created_at=(now or datetime.now(UTC)).astimezone(UTC),
        )
        self.write(
            user_id=user_id,
            state=replace(state, actions=(action, *state.actions)[:20]),
        )
        return action

    def update_profile(self, *, user_id: int, profile: DialogueProfile) -> None:
        state = self.state(user_id=user_id)
        self.write(user_id=user_id, state=replace(state, profile=profile))

    def action(self, *, user_id: int, action_id: str) -> DialogueAction | None:
        return next(
            (action for action in self.state(user_id=user_id).actions if action.id == action_id),
            None,
        )

    def latest_action(
        self,
        *,
        user_id: int,
        kinds: set[str] | None = None,
    ) -> DialogueAction | None:
        return next(
            (
                action
                for action in self.state(user_id=user_id).actions
                if kinds is None or action.kind in kinds
            ),
            None,
        )

    def _state_path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "dialogue" / "state.json"


class ShoppingListStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def add(
        self,
        *,
        user_id: int,
        items: list[str],
        now: datetime | None = None,
    ) -> list[ShoppingItem]:
        created = (now or datetime.now(UTC)).astimezone(UTC)
        existing = self.list_items(user_id=user_id)
        existing_text = {_normalize(item.text) for item in existing}
        additions = [
            ShoppingItem(id=secrets.token_hex(3), text=item, added_at=created)
            for item in items
            if _normalize(item) not in existing_text
        ]
        self._write(user_id=user_id, items=[*existing, *additions])
        return additions

    def list_items(self, *, user_id: int) -> list[ShoppingItem]:
        path = self._path(user_id)
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        items: list[ShoppingItem] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                items.append(
                    ShoppingItem(
                        id=str(item["id"]),
                        text=str(item["text"]),
                        added_at=datetime.fromisoformat(str(item["added_at"])).astimezone(UTC),
                    )
                )
            except (KeyError, ValueError):
                continue
        return items

    def remove_ids(self, *, user_id: int, item_ids: set[str]) -> int:
        items = self.list_items(user_id=user_id)
        remaining = [item for item in items if item.id not in item_ids]
        removed = len(items) - len(remaining)
        if removed:
            self._write(user_id=user_id, items=remaining)
        return removed

    def remove_named(self, *, user_id: int, text: str) -> int:
        target = _normalize(text)
        items = self.list_items(user_id=user_id)
        matched = {
            item.id
            for item in items
            if target in _normalize(item.text) or _normalize(item.text) in target
        }
        return self.remove_ids(user_id=user_id, item_ids=matched)

    def _write(self, *, user_id: int, items: list[ShoppingItem]) -> None:
        atomic_write_text(
            self._path(user_id),
            json.dumps(
                [
                    {"id": item.id, "text": item.text, "added_at": item.added_at.isoformat()}
                    for item in items
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )

    def _path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "dialogue" / "shopping-list.json"


class FactRevisionStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def set(
        self,
        *,
        user_id: int,
        subject: str,
        value: str,
        now: datetime | None = None,
    ) -> FactRevision:
        revision = FactRevision(
            subject=subject.strip(),
            value=value.strip(),
            updated_at=(now or datetime.now(UTC)).astimezone(UTC),
        )
        existing = [
            item
            for item in self.list_revisions(user_id=user_id)
            if _normalize(item.subject) != _normalize(revision.subject)
        ]
        self._write(user_id=user_id, revisions=[revision, *existing])
        return revision

    def matching(self, *, user_id: int, question: str) -> FactRevision | None:
        question_terms = _fact_terms(question)
        for revision in self.list_revisions(user_id=user_id):
            subject_terms = _fact_terms(revision.subject)
            if subject_terms and (
                subject_terms <= question_terms
                or (len(subject_terms) == 1 and bool(subject_terms & question_terms))
            ):
                return revision
        return None

    def remove_from_note(self, *, user_id: int, text: str) -> None:
        match = re.match(r"^Актуально:\s*(.+?)\s*=\s*(.+?)[.]?$", text.strip())
        if match is None:
            return
        subject = _normalize(match.group(1))
        value = _normalize(match.group(2))
        remaining = [
            item
            for item in self.list_revisions(user_id=user_id)
            if _normalize(item.subject) != subject or _normalize(item.value) != value
        ]
        self._write(user_id=user_id, revisions=remaining)

    def list_revisions(self, *, user_id: int) -> list[FactRevision]:
        path = self._path(user_id)
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        revisions: list[FactRevision] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                revisions.append(
                    FactRevision(
                        subject=str(item["subject"]),
                        value=str(item["value"]),
                        updated_at=datetime.fromisoformat(str(item["updated_at"])).astimezone(UTC),
                    )
                )
            except (KeyError, ValueError):
                continue
        return revisions

    def _write(self, *, user_id: int, revisions: list[FactRevision]) -> None:
        atomic_write_text(
            self._path(user_id),
            json.dumps(
                [
                    {
                        "subject": item.subject,
                        "value": item.value,
                        "updated_at": item.updated_at.isoformat(),
                    }
                    for item in revisions
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )

    def _path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "dialogue" / "fact-revisions.json"


class ChatDialogueEngine:
    def __init__(self, vault_path: str, *, timezone_name: str = "Europe/Moscow") -> None:
        self.vault_path = vault_path
        self.timezone_name = timezone_name
        self.memory = ObsidianMemory(vault_path)
        self.finance = FinanceStore(vault_path)
        self.spending = SpendingStore(vault_path)
        self.dialogue = ChatDialogueStore(vault_path)
        self.shopping = ShoppingListStore(vault_path)
        self.revisions = FactRevisionStore(vault_path)
        self.jobs = AssistantJobStore(vault_path, timezone_name=timezone_name)
        self.audit = AuditLogStore(vault_path)

    def handle_text(
        self,
        *,
        user_id: int,
        text: str,
        now: datetime | None = None,
    ) -> ChatReply:
        clean = " ".join(text.strip().split()) if "\n" not in text else text.strip()
        if not clean:
            return ChatReply("")
        state = self.dialogue.state(user_id=user_id)
        normalized = _normalize(clean)
        if normalized in {"отмена", "отмени", "не надо", "cancel"} and state.pending is not None:
            self.dialogue.clear_pending(user_id=user_id)
            return ChatReply("Отменил уточнение.")
        if state.pending is not None:
            reply = self._continue_pending(
                user_id=user_id,
                pending=state.pending,
                text=clean,
                profile=state.profile,
                now=now,
            )
            if reply is not None:
                return reply
        profile_reply = self._set_profile_from_text(user_id=user_id, text=clean, state=state)
        if profile_reply is not None:
            return profile_reply
        if " и еще " in normalized or " и ещё " in clean.lower():
            parts = re.split(r"\s+и\s+е[щш][её]\s+", clean, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                first = self._handle_one(
                    user_id=user_id,
                    text=parts[0],
                    profile=state.profile,
                    now=now,
                )
                second = self._handle_one(
                    user_id=user_id,
                    text=parts[1],
                    profile=state.profile,
                    now=now,
                )
                if first is not None and second is not None:
                    return ChatReply(
                        f"{first.text}\n\n{second.text}",
                        rows=(*first.rows, *second.rows),
                    )
        reply = self._handle_one(user_id=user_id, text=clean, profile=state.profile, now=now)
        if reply is not None:
            return reply
        return self._save_note(user_id=user_id, text=clean, note_type=None, now=now)

    def expect_voice_transcript(self, *, user_id: int) -> ChatReply:
        self.dialogue.pending(user_id=user_id, kind="voice_transcript", payload={})
        return ChatReply(
            "Голосовое получено. Автоматическая расшифровка не подключена: "
            "ответь текстом, и я выполню сказанное как обычную команду."
        )

    def expect_photo_receipt(self, *, user_id: int) -> ChatReply:
        self.dialogue.pending(user_id=user_id, kind="photo_receipt", payload={})
        return ChatReply(
            "Фото получено. OCR не подключён: отправь строки чека текстом, "
            "например:\nмагазин: Магнит\nмолоко 89.90\nхлеб 45"
        )

    def confirm_media_text(
        self,
        *,
        user_id: int,
        text: str,
        source: str,
    ) -> ChatReply:
        kind = "confirm_voice" if source == "voice" else "confirm_receipt"
        self.dialogue.pending(user_id=user_id, kind=kind, payload={"text": text})
        label = "Расшифровал голосовое" if source == "voice" else "Распознал чек"
        return ChatReply(
            f"{label}:\n{text}\n\nПодтвердить?",
            rows=(
                (
                    ChatButton("Подтвердить", "chat:apply:pending"),
                    ChatButton("Отмена", "chat:reject:pending"),
                ),
            ),
        )

    def handle_photo_caption(
        self,
        *,
        user_id: int,
        caption: str,
        now: datetime | None = None,
    ) -> ChatReply:
        try:
            return self._save_receipt(user_id=user_id, text=caption, now=now)
        except ValueError:
            return self.handle_text(user_id=user_id, text=caption, now=now)

    def delivered_reminder_reply(
        self,
        *,
        user_id: int,
        reminder_id: str,
        body: str,
        now: datetime | None = None,
    ) -> ChatReply:
        action = self.dialogue.remember_action(
            user_id=user_id,
            kind="delivered_reminder",
            ref=reminder_id,
            label=body,
            payload={"body": body},
            now=now,
        )
        return ChatReply(
            "",
            rows=(
                (
                    ChatButton("Готово", f"chat:remdone:{action.id}"),
                    ChatButton("Через час", f"chat:rempost:{action.id}:60"),
                    ChatButton("Завтра", f"chat:rempost:{action.id}:1440"),
                ),
                (ChatButton("Больше не напоминать", f"chat:remstop:{action.id}"),),
            ),
        )

    def handle_callback(
        self,
        *,
        user_id: int,
        data: str,
        now: datetime | None = None,
    ) -> ChatReply:
        parts = data.split(":")
        if len(parts) < 3 or parts[0] != "chat":
            return ChatReply("Действие не распознано.")
        verb, action_id = parts[1], parts[2]
        if action_id == "pending" and verb in {"apply", "reject"}:
            state = self.dialogue.state(user_id=user_id)
            if state.pending is None or state.pending.kind not in {
                "confirm_voice",
                "confirm_receipt",
            }:
                return ChatReply("Подтверждение уже недоступно.")
            if verb == "reject":
                self.dialogue.clear_pending(user_id=user_id)
                return ChatReply("Отменил распознанное действие.")
            return self._apply_media_pending(user_id=user_id, pending=state.pending, now=now)
        action = self.dialogue.action(user_id=user_id, action_id=action_id)
        if action is None:
            return ChatReply("Это действие уже недоступно.")
        if verb == "undo":
            return self._undo(user_id=user_id, action=action, now=now)
        if action.kind == "delivered_reminder" and verb == "remdone":
            self._audit_change(user_id, "chat_reminder_done", action.label, now=now)
            return ChatReply("Отметил напоминание выполненным.")
        if action.kind == "delivered_reminder" and verb == "remstop":
            self._audit_change(user_id, "chat_reminder_stop", action.label, now=now)
            return ChatReply("Больше не буду повторять это напоминание.")
        if action.kind == "delivered_reminder" and verb == "rempost":
            minutes = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 60
            due_at = (now or datetime.now(UTC)).astimezone(UTC) + timedelta(minutes=minutes)
            self._audit_change(user_id, "chat_reminder_postpone", action.label, now=now)
            return self._save_reminder(
                user_id=user_id,
                body=action.payload.get("body", action.label),
                due_at=due_at,
                now=now,
            )
        if verb == "done" and action.kind == "task":
            if self.memory.complete_task(user_id=user_id, task_id=action.ref):
                self._audit_change(user_id, "chat_task_complete", action.label, now=now)
                return ChatReply("Готово. Задача закрыта.")
            return ChatReply("Задача уже закрыта или удалена.")
        if verb == "edit" and action.kind == "expense":
            self.dialogue.pending(
                user_id=user_id,
                kind="expense_category",
                payload={"transaction_id": action.ref},
            )
            return ChatReply("Напиши новую категорию расхода.")
        if verb == "edit" and action.kind == "reminder":
            self.dialogue.pending(
                user_id=user_id,
                kind="edit_reminder_when",
                payload={"reminder_id": action.ref, "body": action.payload.get("body", "")},
            )
            return ChatReply("Когда теперь напомнить? Например: завтра в 18.")
        if verb == "snooze" and action.kind == "reminder":
            minutes = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 60
            reminder = next(
                (
                    item
                    for item in self.memory.list_reminders(user_id=user_id, limit=100)
                    if item.id == action.ref
                ),
                None,
            )
            if reminder is None:
                return ChatReply("Напоминание уже недоступно.")
            body = action.payload.get("body") or reminder.snippet
            self.memory.delete_note(user_id=user_id, note_id=reminder.id)
            path = self.memory.create_reminder(
                user_id=user_id,
                text=body,
                due_at=reminder.due_at + timedelta(minutes=minutes),
            )
            local = reminder.due_at.astimezone(ZoneInfo(self.timezone_name)) + timedelta(
                minutes=minutes
            )
            new_action = self.dialogue.remember_action(
                user_id=user_id,
                kind="reminder",
                ref=path.stem,
                label=body,
                payload={"body": body},
                now=now,
            )
            self._audit_change(user_id, "chat_reminder_snooze", body, now=now)
            return ChatReply(
                f"Отложил до {local:%d.%m %H:%M}.",
                rows=self._rows(new_action, allow_edit=True, allow_snooze=True),
            )
        if verb == "forget":
            return ChatReply(
                f"Удалить из памяти: «{action.label[:100]}»?",
                rows=(
                    (
                        ChatButton("Удалить", f"chat:delete:{action.id}"),
                        ChatButton("Оставить", f"chat:keep:{action.id}"),
                    ),
                ),
            )
        if verb == "delete" and action.kind in {"note", "preference", "memory_reference"}:
            deleted = self.memory.delete_note(user_id=user_id, note_id=action.ref)
            if deleted:
                self.revisions.remove_from_note(user_id=user_id, text=action.label)
                self._audit_change(user_id, "chat_memory_delete", action.label, now=now)
            return ChatReply("Удалил из памяти." if deleted else "Запись уже удалена.")
        if verb == "keep":
            return ChatReply("Оставил запись без изменений.")
        return ChatReply("Для этого действия изменение пока не поддерживается.")

    def _handle_one(
        self,
        *,
        user_id: int,
        text: str,
        profile: DialogueProfile,
        now: datetime | None,
    ) -> ChatReply | None:
        normalized = _normalize(text)
        if normalized in {"доброе утро", "утренняя сводка", "что на сегодня"}:
            return ChatReply("Готовлю утреннюю сводку.", event="morning")
        if normalized in {"добрый вечер", "вечерняя сводка", "подведи итоги дня"}:
            return ChatReply("Готовлю вечерний обзор.", event="evening")
        if normalized in {"что у меня сегодня", "покажи дела на сегодня", "мои дела"}:
            return ChatReply("Показываю план.", event="agenda")
        if normalized in {
            "покажи что ты сегодня запомнил",
            "покажи, что ты сегодня запомнил",
            "что ты сегодня запомнил",
            "покажи память за сегодня",
        }:
            return ChatReply(self.memory.today_digest(user_id=user_id, created_at=now))
        if normalized in {
            "покажи историю изменений",
            "история изменений",
            "что ты изменил",
        }:
            return self._change_history(user_id=user_id)
        scheduled_brief = self._set_brief_schedule(user_id=user_id, text=text, now=now)
        if scheduled_brief is not None:
            return scheduled_brief
        if normalized in {
            "отмени последнюю запись",
            "отмени последнее действие",
            "удали последнюю запись",
        }:
            latest = self.dialogue.latest_action(
                user_id=user_id,
                kinds={
                    "note",
                    "preference",
                    "task",
                    "reminder",
                    "expense",
                    "receipt",
                    "shopping",
                },
            )
            if latest is None:
                return ChatReply("Последнего действия для отмены не нашёл.")
            return self._undo(user_id=user_id, action=latest, now=now)
        if "сколько" in normalized and any(word in normalized for word in ("потрат", "расход")):
            return self._expense_summary(user_id=user_id, text=text, now=now)
        if normalized in {"что купить", "что в покупках", "список покупок", "покажи покупки"}:
            return self._shopping_list(user_id=user_id)
        removed = re.match(r"^(?:убери|удали)\s+(.+?)\s+из\s+(?:списка\s+)?покуп", normalized)
        if removed:
            count = self.shopping.remove_named(user_id=user_id, text=removed.group(1))
            return ChatReply("Убрал из покупок." if count else "Такого товара в покупках нет.")
        shopping = re.match(
            r"^(?:добавь|запиши)\s+(.+?)\s+в\s+(?:список\s+)?покуп(?:ок|ки)$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if shopping:
            return self._add_shopping(user_id=user_id, text=shopping.group(1), now=now)
        transfer = re.search(r"не\s+расход\s*,?\s+а\s+перевод", normalized)
        if transfer:
            latest = self.dialogue.latest_action(user_id=user_id, kinds={"expense"})
            if latest and self.finance.delete_transaction(
                user_id=user_id,
                transaction_id=latest.ref,
            ):
                self._audit_change(user_id, "chat_expense_remove_transfer", latest.label, now=now)
                return ChatReply("Убрал последний расход. Переводы не учитываю в расходах.")
            return ChatReply("Последнего расхода для исправления не нашёл.")
        if normalized in {"этот расход был вчера", "последний расход был вчера"}:
            return self._move_latest_expense_to_yesterday(user_id=user_id, now=now)
        category_edit = re.match(r"^(?:исправь|измени)\s+категори\w*\s+на\s+(.+)$", normalized)
        if category_edit:
            latest = self.dialogue.latest_action(user_id=user_id, kinds={"expense"})
            if latest is None:
                return ChatReply("Последнего расхода для изменения не нашёл.")
            return self._change_category(
                user_id=user_id,
                transaction_id=latest.ref,
                category=category_edit.group(1),
                now=now,
            )
        if normalized in {"забудь это", "это больше не актуально", "удали это из памяти"}:
            action = self.dialogue.latest_action(
                user_id=user_id,
                kinds={"note", "preference", "memory_reference"},
            )
            if action is None:
                return ChatReply("Не вижу последней записи памяти, которую можно удалить.")
            return ChatReply(
                f"Удалить из памяти: «{action.label[:100]}»?",
                rows=(
                    (
                        ChatButton("Удалить", f"chat:delete:{action.id}"),
                        ChatButton("Оставить", f"chat:keep:{action.id}"),
                    ),
                ),
            )
        expense = re.match(
            r"^(?:я\s+)?(?:потратил[аи]?|запиши\s+расход|расход)\s+"
            r"(?P<amount>\d+(?:[.,]\d{1,2})?)\s*(?:₽|руб(?:лей|ля|ль)?\.?)?"
            r"(?:\s+(?:на|за)\s+)?(?P<category>.*)$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if expense:
            amount = parse_amount(expense.group("amount"))
            category = expense.group("category").strip()
            if not category:
                self.dialogue.pending(
                    user_id=user_id,
                    kind="expense_category_new",
                    payload={"amount": str(amount)},
                )
                return ChatReply(f"На какую категорию записать расход {format_money(amount)}?")
            return self._save_expense(user_id=user_id, amount=amount, category=category, now=now)
        reminder = re.match(
            r"^(?:напомни(?:\s+мне)?|поставь\s+напоминание)\s+(.+)$",
            text.strip(),
            re.I,
        )
        if reminder:
            return self._new_reminder(
                user_id=user_id,
                raw=reminder.group(1),
                profile=profile,
                now=now,
            )
        dated_task = re.match(
            r"^(?P<date>сегодня|завтра)\s+(?:мне\s+)?"
            r"(?:надо|нужно)\s+(?P<body>.+)$",
            normalized,
        )
        if dated_task:
            self.dialogue.pending(
                user_id=user_id,
                kind="reminder_when",
                payload={"body": dated_task.group("body"), "date_hint": dated_task.group("date")},
            )
            return ChatReply(
                f"Во сколько {dated_task.group('date')} напомнить: "
                f"«{dated_task.group('body')}»?"
            )
        task = re.match(
            r"^(?:добавь\s+(?:задачу|дело)|задача\s*:|мне\s+надо|надо|нужно)\s+(.+)$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if task:
            return self._save_task(user_id=user_id, text=task.group(1), now=now)
        if normalized in {"готово", "сделано", "задача сделана"}:
            latest = self.dialogue.latest_action(user_id=user_id, kinds={"task"})
            if latest and self.memory.complete_task(user_id=user_id, task_id=latest.ref):
                return ChatReply("Готово. Задача закрыта.")
            delivered = self.dialogue.latest_action(user_id=user_id, kinds={"delivered_reminder"})
            if delivered:
                self._audit_change(user_id, "chat_reminder_done", delivered.label, now=now)
                return ChatReply("Отметил напоминание выполненным.")
        if normalized in {"завтра", "напомни завтра", "через час", "больше не напоминай"}:
            delivered = self.dialogue.latest_action(user_id=user_id, kinds={"delivered_reminder"})
            if delivered:
                if normalized == "больше не напоминай":
                    self._audit_change(user_id, "chat_reminder_stop", delivered.label, now=now)
                    return ChatReply("Больше не буду повторять это напоминание.")
                delta = timedelta(hours=1) if normalized == "через час" else timedelta(days=1)
                return self._save_reminder(
                    user_id=user_id,
                    body=delivered.payload.get("body", delivered.label),
                    due_at=(now or datetime.now(UTC)).astimezone(UTC) + delta,
                    now=now,
                )
        correction = re.match(
            r"^(?:замени|исправь)\s+(.+?)\s+на\s+(.+)$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if correction:
            self.revisions.set(
                user_id=user_id,
                subject=correction.group(1),
                value=correction.group(2),
                now=now,
            )
            return self._save_note(
                user_id=user_id,
                text=f"Актуально: {correction.group(1)} = {correction.group(2)}",
                note_type="preference",
                now=now,
            )
        remember = re.match(
            r"^(?:запомни|запиши|сохрани|учти)\s*,?\s*(?:что\s+)?(.+)$",
            text.strip(),
            flags=re.IGNORECASE,
        )
        if remember:
            body = remember.group(1).strip()
            note_type = (
                "preference"
                if re.search(r"предпочит|люблю|нравится|обычно|всегда", _normalize(body))
                else "note"
            )
            return self._save_note(user_id=user_id, text=body, note_type=note_type, now=now)
        if _looks_like_memory_question(normalized):
            return self._answer_memory(
                user_id=user_id,
                question=text,
                concise=profile.concise,
                now=now,
            )
        return None

    def _continue_pending(
        self,
        *,
        user_id: int,
        pending: PendingDialogue,
        text: str,
        profile: DialogueProfile,
        now: datetime | None,
    ) -> ChatReply | None:
        if pending.kind in {"confirm_voice", "confirm_receipt"}:
            if _normalize(text) in {"да", "подтверди", "подтверждаю", "верно"}:
                return self._apply_media_pending(user_id=user_id, pending=pending, now=now)
            return ChatReply("Подтверди распознанный текст или напиши «отмена».")
        if pending.kind == "voice_transcript":
            self.dialogue.clear_pending(user_id=user_id)
            reply = self._handle_one(user_id=user_id, text=text, profile=profile, now=now)
            return reply or self._save_note(user_id=user_id, text=text, note_type="voice", now=now)
        if pending.kind == "photo_receipt":
            try:
                reply = self._save_receipt(user_id=user_id, text=text, now=now)
            except ValueError as exc:
                return ChatReply(
                    f"Чек пока не распознан: {exc}\n"
                    "Отправь строки вида «товар 123.45»."
                )
            self.dialogue.clear_pending(user_id=user_id)
            return reply
        if pending.kind == "expense_category_new":
            self.dialogue.clear_pending(user_id=user_id)
            return self._save_expense(
                user_id=user_id,
                amount=parse_amount(pending.payload["amount"]),
                category=text,
                now=now,
            )
        if pending.kind == "expense_category":
            self.dialogue.clear_pending(user_id=user_id)
            return self._change_category(
                user_id=user_id,
                transaction_id=pending.payload["transaction_id"],
                category=text,
                now=now,
            )
        if pending.kind in {"reminder_when", "edit_reminder_when"}:
            body = pending.payload.get("body", "")
            date_hint = pending.payload.get("date_hint")
            try:
                due_at = _parse_when(
                    text,
                    body=body,
                    date_hint=date_hint,
                    profile=profile,
                    timezone_name=self.timezone_name,
                    now=now,
                )
            except ValueError:
                return ChatReply("Не понял время. Напиши, например: завтра в 18 или через 2 часа.")
            self.dialogue.clear_pending(user_id=user_id)
            if pending.kind == "edit_reminder_when":
                self.memory.delete_note(user_id=user_id, note_id=pending.payload["reminder_id"])
            return self._save_reminder(user_id=user_id, body=body, due_at=due_at, now=now)
        return None

    def _apply_media_pending(
        self,
        *,
        user_id: int,
        pending: PendingDialogue,
        now: datetime | None,
    ) -> ChatReply:
        text = pending.payload.get("text", "")
        self.dialogue.clear_pending(user_id=user_id)
        if pending.kind == "confirm_voice":
            return self.handle_text(user_id=user_id, text=text, now=now)
        try:
            return self._save_receipt(user_id=user_id, text=text, now=now)
        except ValueError as exc:
            self.dialogue.pending(user_id=user_id, kind="photo_receipt", payload={})
            return ChatReply(
                f"Не удалось сохранить распознанный чек: {exc}\n"
                "Отправь исправленные строки вида «товар 123.45»."
            )

    def _set_brief_schedule(
        self,
        *,
        user_id: int,
        text: str,
        now: datetime | None,
    ) -> ChatReply | None:
        normalized = _normalize(text)
        stop = re.match(
            r"^(?:не\s+присылай|отключи)\s+(?P<period>утренн\w+|вечерн\w+)\s+"
            r"(?:сводк\w+|обзор\w+|итог\w*)$",
            normalized,
        )
        if stop:
            mode = "morning" if stop.group("period").startswith("утрен") else "evening"
            removed = self._remove_daily_brief(user_id=user_id, delivery_mode=mode)
            return ChatReply(
                "Отключил ежедневную сводку." if removed else "Такая рассылка не включена."
            )
        match = re.match(
            r"^(?:присылай|отправляй)\s+(?:мне\s+)?"
            r"(?P<period>утренн\w+|вечерн\w+)\s+"
            r"(?:сводк\w+|обзор\w+|итог\w*)\s+(?:каждый\s+день\s+)?"
            r"в\s+(?P<clock>\d{1,2}(?::\d{2})?)$",
            normalized,
        )
        if match is None:
            match = re.match(
                r"^кажд\w+\s+(?P<period>утр\w*|вечер\w*)\s+"
                r"в\s+(?P<clock>\d{1,2}(?::\d{2})?)\s+"
                r"(?:присылай|отправляй|подводи).*$",
                normalized,
            )
        if match is None:
            return None
        clock = match.group("clock")
        if ":" not in clock:
            clock = f"{clock}:00"
        mode = "morning" if match.group("period").startswith("утр") else "evening"
        try:
            hour, minute = (int(part) for part in clock.split(":"))
            clock = f"{hour:02d}:{minute:02d}"
            self._remove_daily_brief(user_id=user_id, delivery_mode=mode)
            self.jobs.add_job(
                user_id=user_id,
                schedule_type="daily",
                schedule_value=clock,
                delivery_mode=mode,
                message=f"{mode} brief",
                now=now,
            )
        except ValueError:
            return ChatReply("Укажи корректное время, например 08:00 или 20:30.")
        label = "утреннюю" if mode == "morning" else "вечернюю"
        self._audit_change(user_id, "chat_brief_schedule", f"{mode} {clock}", now=now)
        return ChatReply(f"Буду присылать {label} сводку каждый день в {clock}.")

    def _remove_daily_brief(self, *, user_id: int, delivery_mode: str) -> bool:
        removed = False
        for job in self.jobs.list_jobs(user_id=user_id):
            if job.delivery_mode == delivery_mode and job.schedule_type == "daily":
                removed = self.jobs.delete_job(user_id=user_id, job_id=job.id) or removed
        return removed

    def _set_profile_from_text(
        self,
        *,
        user_id: int,
        text: str,
        state: DialogueState,
    ) -> ChatReply | None:
        normalized = _normalize(text)
        if normalized in {"отвечай короче", "отвечай кратко", "короткие ответы"}:
            self.dialogue.update_profile(
                user_id=user_id,
                profile=replace(state.profile, concise=True),
            )
            return ChatReply("Буду отвечать короче.")
        if normalized in {"отвечай подробнее", "подробные ответы"}:
            self.dialogue.update_profile(
                user_id=user_id,
                profile=replace(state.profile, concise=False),
            )
            return ChatReply("Буду давать более подробные ответы.")
        match = re.search(r"вечером\s+(?:это|считай)\s+(?:в\s+)?(\d{1,2})(?::\d{2})?", normalized)
        if match:
            hour = int(match.group(1))
            if not 0 <= hour <= 23:
                return ChatReply("Час должен быть от 0 до 23.")
            self.dialogue.update_profile(
                user_id=user_id,
                profile=replace(state.profile, evening_hour=hour),
            )
            return ChatReply(f"Буду понимать «вечером» как {hour:02d}:00.")
        return None

    def _new_reminder(
        self,
        *,
        user_id: int,
        raw: str,
        profile: DialogueProfile,
        now: datetime | None,
    ) -> ChatReply:
        try:
            due_at, body = _parse_reminder_text(
                raw,
                profile=profile,
                timezone_name=self.timezone_name,
                now=now,
            )
        except ValueError:
            self.dialogue.pending(user_id=user_id, kind="reminder_when", payload={"body": raw})
            return ChatReply(f"Когда напомнить: «{raw}»?")
        return self._save_reminder(user_id=user_id, body=body, due_at=due_at, now=now)

    def _save_reminder(
        self,
        *,
        user_id: int,
        body: str,
        due_at: datetime,
        now: datetime | None,
    ) -> ChatReply:
        path = self.memory.create_reminder(
            user_id=user_id,
            text=body,
            due_at=due_at,
            created_at=now,
        )
        action = self.dialogue.remember_action(
            user_id=user_id,
            kind="reminder",
            ref=path.stem,
            label=body,
            payload={"body": body},
            now=now,
        )
        self._audit_change(user_id, "chat_reminder_create", body, now=now)
        local = due_at.astimezone(ZoneInfo(self.timezone_name))
        return ChatReply(
            f"Напомню {local:%d.%m.%Y в %H:%M}: {body}.",
            rows=self._rows(action, allow_edit=True, allow_snooze=True),
        )

    def _save_task(self, *, user_id: int, text: str, now: datetime | None) -> ChatReply:
        path = self.memory.create_task(user_id=user_id, text=text, created_at=now)
        action = self.dialogue.remember_action(
            user_id=user_id,
            kind="task",
            ref=path.stem,
            label=text,
            now=now,
        )
        self._audit_change(user_id, "chat_task_create", text, now=now)
        return ChatReply(
            f"Добавил задачу: {text}.",
            rows=self._rows(action, allow_done=True),
        )

    def _save_note(
        self,
        *,
        user_id: int,
        text: str,
        note_type: str | None,
        now: datetime | None,
    ) -> ChatReply:
        if note_type == "preference":
            path = self.memory.remember_preference(user_id=user_id, text=text, created_at=now)
            label = "Сохранил предпочтение"
            kind = "preference"
        else:
            path = self.memory.remember_user_note(
                user_id=user_id,
                text=text,
                note_type=note_type,
                created_at=now,
            )
            label = "Запомнил"
            kind = "note"
        action = self.dialogue.remember_action(
            user_id=user_id,
            kind=kind,
            ref=path.stem,
            label=text,
            now=now,
        )
        self._audit_change(user_id, "chat_memory_create", text, now=now)
        return ChatReply(f"{label}: {text}.", rows=self._rows(action))

    def _save_expense(
        self,
        *,
        user_id: int,
        amount: Decimal,
        category: str,
        now: datetime | None,
    ) -> ChatReply:
        transaction = self.finance.add_transaction(
            user_id=user_id,
            kind="expense",
            amount=amount,
            category=category,
            created_at=now,
        )
        action = self.dialogue.remember_action(
            user_id=user_id,
            kind="expense",
            ref=transaction.id,
            label=f"{format_money(amount)} / {category}",
            payload={"category": category},
            now=now,
        )
        self._audit_change(user_id, "chat_expense_create", action.label, now=now)
        return ChatReply(
            f"Записал расход: {format_money(amount)}, категория «{category}».",
            rows=self._rows(action, allow_edit=True),
        )

    def _change_category(
        self,
        *,
        user_id: int,
        transaction_id: str,
        category: str,
        now: datetime | None,
    ) -> ChatReply:
        transaction = self.finance.update_transaction_category(
            user_id=user_id,
            transaction_id=transaction_id,
            category=category,
        )
        if transaction is None:
            return ChatReply("Расход для изменения уже недоступен.")
        self._audit_change(
            user_id,
            "chat_expense_category",
            f"{transaction.id}: {transaction.category}",
            now=now,
        )
        return ChatReply(f"Категория расхода изменена на «{transaction.category}».")

    def _save_receipt(self, *, user_id: int, text: str, now: datetime | None) -> ChatReply:
        store, items = parse_receipt_text(text)
        receipt = self.spending.add_receipt(
            user_id=user_id,
            store=store,
            items=items,
            purchased_at=now,
        )
        action = self.dialogue.remember_action(
            user_id=user_id,
            kind="receipt",
            ref=receipt.id,
            label=f"{receipt.store}: {receipt.total}",
            now=now,
        )
        self._audit_change(user_id, "chat_receipt_create", action.label, now=now)
        return ChatReply(format_receipt(receipt), rows=self._rows(action))

    def _answer_memory(
        self,
        *,
        user_id: int,
        question: str,
        concise: bool,
        now: datetime | None,
    ) -> ChatReply:
        revision = self.revisions.matching(user_id=user_id, question=question)
        if revision is not None:
            matching_results = self.memory.search_user_notes(
                user_id=user_id,
                query=revision.value,
                limit=1,
            )
            lines = [f"Актуально: {revision.subject} = {revision.value}."]
            if not matching_results:
                return ChatReply("\n".join(lines))
            top = matching_results[0]
            lines.append(f"Источник: {top.citation}")
            action = self.dialogue.remember_action(
                user_id=user_id,
                kind="memory_reference",
                ref=top.path.stem,
                label=top.snippet,
                now=now,
            )
            return ChatReply(
                "\n".join(lines),
                rows=((ChatButton("Забыть найденное", f"chat:forget:{action.id}"),),),
            )
        results = self.memory.search_user_notes(user_id=user_id, query=question, limit=3)
        if not results:
            return ChatReply("В памяти пока нет подходящей информации.")
        shown = results[:1] if concise else results
        lines = ["Нашёл в памяти:"]
        for result in shown:
            lines.append(f"- {result.snippet}\n  Источник: {result.citation}")
        top = shown[0]
        action = self.dialogue.remember_action(
            user_id=user_id,
            kind="memory_reference",
            ref=top.path.stem,
            label=top.snippet,
            now=now,
        )
        return ChatReply(
            "\n".join(lines),
            rows=((ChatButton("Забыть найденное", f"chat:forget:{action.id}"),),),
        )

    def _add_shopping(self, *, user_id: int, text: str, now: datetime | None) -> ChatReply:
        items = [
            item.strip(" .,")
            for item in re.split(r",|\s+и\s+", text, flags=re.IGNORECASE)
            if item.strip(" .,")
        ]
        additions = self.shopping.add(user_id=user_id, items=items, now=now)
        if not additions:
            return ChatReply("Эти товары уже есть в списке покупок.")
        action = self.dialogue.remember_action(
            user_id=user_id,
            kind="shopping",
            ref=",".join(item.id for item in additions),
            label=", ".join(item.text for item in additions),
            now=now,
        )
        self._audit_change(user_id, "chat_shopping_add", action.label, now=now)
        return ChatReply(
            "Добавил в покупки: " + ", ".join(item.text for item in additions) + ".",
            rows=self._rows(action),
        )

    def _shopping_list(self, *, user_id: int) -> ChatReply:
        items = self.shopping.list_items(user_id=user_id)
        if not items:
            return ChatReply("Список покупок пуст.")
        return ChatReply("Покупки:\n" + "\n".join(f"- {item.text}" for item in items))

    def _expense_summary(
        self,
        *,
        user_id: int,
        text: str,
        now: datetime | None,
    ) -> ChatReply:
        local = (now or datetime.now(UTC)).astimezone(ZoneInfo(self.timezone_name))
        month = local.strftime("%Y-%m")
        category_match = re.search(r"\bна\s+(.+?)(?:\s+в\s+этом\s+месяце)?\??$", text, re.I)
        category = category_match.group(1).strip(" ?") if category_match else ""
        transactions = self.finance.list_transactions(
            user_id=user_id,
            kind="expense",
            month=month,
            limit=10_000,
        )
        if category:
            normalized = _normalize(category)
            transactions = [
                item for item in transactions if normalized in _normalize(item.category)
            ]
        total = sum((item.amount for item in transactions), Decimal("0"))
        suffix = f" на «{category}»" if category else ""
        return ChatReply(f"За {month} расходов{suffix}: {format_money(total)}.")

    def _undo(
        self,
        *,
        user_id: int,
        action: DialogueAction,
        now: datetime | None = None,
    ) -> ChatReply:
        if action.kind in {"note", "preference", "task", "reminder"}:
            removed = self.memory.delete_note(user_id=user_id, note_id=action.ref)
        elif action.kind == "expense":
            removed = self.finance.delete_transaction(user_id=user_id, transaction_id=action.ref)
        elif action.kind == "receipt":
            removed = self.spending.delete_receipt(user_id=user_id, receipt_id=action.ref)
        elif action.kind == "shopping":
            removed = bool(
                self.shopping.remove_ids(user_id=user_id, item_ids=set(action.ref.split(",")))
            )
        else:
            removed = False
        if removed:
            if action.kind in {"note", "preference"}:
                self.revisions.remove_from_note(user_id=user_id, text=action.label)
            self._audit_change(user_id, "chat_undo", f"{action.kind}: {action.label}", now=now)
        return ChatReply("Отменил последнее действие." if removed else "Действие уже отменено.")

    def _move_latest_expense_to_yesterday(
        self,
        *,
        user_id: int,
        now: datetime | None,
    ) -> ChatReply:
        action = self.dialogue.latest_action(user_id=user_id, kinds={"expense"})
        if action is None:
            return ChatReply("Последнего расхода для изменения не нашёл.")
        transaction = next(
            (
                item
                for item in self.finance.list_transactions(user_id=user_id, limit=10_000)
                if item.id == action.ref
            ),
            None,
        )
        if transaction is None:
            return ChatReply("Последнего расхода для изменения не нашёл.")
        timezone = ZoneInfo(self.timezone_name)
        current = (now or datetime.now(UTC)).astimezone(timezone)
        yesterday = (current - timedelta(days=1)).date()
        original_local = transaction.created_at.astimezone(timezone)
        changed_local = original_local.replace(
            year=yesterday.year,
            month=yesterday.month,
            day=yesterday.day,
        )
        updated = self.finance.update_transaction_created_at(
            user_id=user_id,
            transaction_id=transaction.id,
            created_at=changed_local.astimezone(UTC),
        )
        if updated is None:
            return ChatReply("Последнего расхода для изменения не нашёл.")
        self._audit_change(user_id, "chat_expense_date", action.label, now=now)
        return ChatReply(f"Перенёс последний расход на {changed_local:%d.%m.%Y}.")

    def _change_history(self, *, user_id: int) -> ChatReply:
        events = [
            event
            for event in self.audit.list_events(user_id=user_id, limit=50)
            if event.action.startswith("chat_")
        ][:10]
        if not events:
            return ChatReply("История диалоговых изменений пока пуста.")
        lines = ["Последние изменения:"]
        timezone = ZoneInfo(self.timezone_name)
        for event in events:
            local = event.created_at.astimezone(timezone)
            action = event.action.removeprefix("chat_")
            lines.append(f"- {local:%d.%m %H:%M} {action}: {event.detail}")
        return ChatReply("\n".join(lines))

    def _audit_change(
        self,
        user_id: int,
        action: str,
        detail: str,
        *,
        now: datetime | None,
    ) -> None:
        self.audit.record(user_id=user_id, action=action, detail=detail, now=now)

    def _rows(
        self,
        action: DialogueAction,
        *,
        allow_done: bool = False,
        allow_edit: bool = False,
        allow_snooze: bool = False,
    ) -> tuple[tuple[ChatButton, ...], ...]:
        main = [ChatButton("Отменить", f"chat:undo:{action.id}")]
        if allow_done:
            main.append(ChatButton("Готово", f"chat:done:{action.id}"))
        if allow_edit:
            main.append(ChatButton("Изменить", f"chat:edit:{action.id}"))
        rows: list[tuple[ChatButton, ...]] = [tuple(main)]
        if allow_snooze:
            rows.append((ChatButton("Отложить на час", f"chat:snooze:{action.id}:60"),))
        return tuple(rows)


def daily_actions_keyboard() -> tuple[tuple[ChatButton, ...], ...]:
    return (
        (
            ChatButton("Дела", "chat:brief:agenda"),
            ChatButton("Бюджет", "chat:brief:budget"),
        ),
        (
            ChatButton("Утро", "chat:brief:morning"),
            ChatButton("Вечер", "chat:brief:evening"),
        ),
    )


def _looks_like_memory_question(text: str) -> bool:
    return text.startswith(
        (
            "что ",
            "где ",
            "когда ",
            "как ",
            "помнишь",
            "что ты знаешь",
            "найди ",
        )
    )


def _parse_reminder_text(
    raw: str,
    *,
    profile: DialogueProfile,
    timezone_name: str,
    now: datetime | None,
) -> tuple[datetime, str]:
    clean = _normalize_clock(raw, profile=profile)
    try:
        return parse_reminder_request(clean, now=now, timezone_name=timezone_name)
    except ValueError:
        pass
    trailing = re.match(
        r"^(?P<body>.+?)\s+(?P<when>(?:сегодня|завтра)"
        r"(?:\s+(?:\d{1,2}(?::\d{2})?|вечером|после обеда))?|"
        r"через\s+\d+\s+(?:минут[уы]?|мин|час(?:а|ов)?|д(?:ень|ня|ней)?))$",
        clean,
        flags=re.IGNORECASE,
    )
    if trailing:
        when = trailing.group("when")
        body = trailing.group("body")
        return _parse_when_and_body(
            when,
            body=body,
            profile=profile,
            timezone_name=timezone_name,
            now=now,
        )
    raise ValueError("when is missing")


def _parse_when(
    text: str,
    *,
    body: str,
    date_hint: str | None,
    profile: DialogueProfile,
    timezone_name: str,
    now: datetime | None,
) -> datetime:
    when = text.strip()
    if date_hint and re.match(r"^(?:в\s+)?\d{1,2}(?::\d{2})?$", when, flags=re.I):
        when = f"{date_hint} {when.removeprefix('в ').strip()}"
    return _parse_when_and_body(
        when,
        body=body,
        profile=profile,
        timezone_name=timezone_name,
        now=now,
    )[0]


def _parse_when_and_body(
    when: str,
    *,
    body: str,
    profile: DialogueProfile,
    timezone_name: str,
    now: datetime | None,
) -> tuple[datetime, str]:
    clean_when = _normalize_clock(when, profile=profile)
    weekday = re.match(
        r"^в?\s*(понедельник|вторник|сред[ау]|четверг|пятниц[ау]|суббот[ау]|воскресенье)"
        r"(?:\s+(?:в\s+)?(\d{1,2}(?::\d{2})?|вечером|после обеда))?$",
        _normalize(clean_when),
    )
    if weekday:
        timezone = ZoneInfo(timezone_name)
        current = (now or datetime.now(timezone)).astimezone(timezone)
        weekdays = {
            "понедельник": 0,
            "вторник": 1,
            "среда": 2,
            "среду": 2,
            "четверг": 3,
            "пятница": 4,
            "пятницу": 4,
            "суббота": 5,
            "субботу": 5,
            "воскресенье": 6,
        }
        target = weekdays[weekday.group(1)]
        offset = (target - current.weekday()) % 7 or 7
        clock = weekday.group(2) or f"{profile.evening_hour:02d}:00"
        clock = _clock_for_word(clock, profile=profile)
        hour, minute = [int(part) for part in clock.split(":")]
        due = (current + timedelta(days=offset)).replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
        return due.astimezone(UTC), body
    if re.match(r"^(?:в\s+)?\d{1,2}(?::\d{2})?$", clean_when, flags=re.I):
        timezone = ZoneInfo(timezone_name)
        current = (now or datetime.now(timezone)).astimezone(timezone)
        clock = clean_when.lower().removeprefix("в ").strip()
        if ":" not in clock:
            clock += ":00"
        hour, minute = [int(part) for part in clock.split(":")]
        due = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due <= current:
            due += timedelta(days=1)
        return due.astimezone(UTC), body
    due_at, _ = parse_reminder_request(
        f"{clean_when} {body}",
        now=now,
        timezone_name=timezone_name,
    )
    return due_at, body


def _normalize_clock(text: str, *, profile: DialogueProfile) -> str:
    clean = re.sub(r"\s+", " ", text.strip())
    clean = re.sub(
        r"\b(сегодня|завтра)\s+в\s+(\d{1,2})(?![:\d])",
        lambda match: f"{match.group(1)} {int(match.group(2)):02d}:00",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(
        r"\b(сегодня|завтра)\s+(\d{1,2})(?![:\d])",
        lambda match: f"{match.group(1)} {int(match.group(2)):02d}:00",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(
        r"\b(сегодня|завтра)\s+вечером\b",
        lambda match: f"{match.group(1)} {profile.evening_hour:02d}:00",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(
        r"\b(сегодня|завтра)\s+после обеда\b",
        lambda match: f"{match.group(1)} {profile.afternoon_hour:02d}:00",
        clean,
        flags=re.IGNORECASE,
    )
    return clean


def _clock_for_word(value: str, *, profile: DialogueProfile) -> str:
    if value == "вечером":
        return f"{profile.evening_hour:02d}:00"
    if value == "после обеда":
        return f"{profile.afternoon_hour:02d}:00"
    return f"{int(value):02d}:00" if ":" not in value else value


def _hour(value: object, *, default: int) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return default
    return parsed if 0 <= parsed <= 23 else default


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("ё", "е").split()).strip(" .!?")


def _fact_terms(value: str) -> set[str]:
    stopwords = {"что", "как", "где", "когда", "это", "теперь", "актуально"}
    terms: set[str] = set()
    for word in re.findall(r"[a-zа-я0-9]+", _normalize(value)):
        if len(word) < 3 or word in stopwords:
            continue
        prefix = word[:3]
        terms.add("имя" if prefix == "зов" else prefix)
    return terms
