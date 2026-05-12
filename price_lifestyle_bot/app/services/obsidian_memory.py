from __future__ import annotations

import hashlib
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from app.services.basket_parser import BasketItemParsed

STORE_LABELS = {
    "smart": "Smart",
    "magnit": "Магнит",
    "spar": "SPAR",
    "pyaterochka": "Пятёрочка",
    "fix_price": "Fix Price",
}

STORE_ALIASES = {
    "smart": ("smart", "смарт", "сладкая жизнь"),
    "magnit": ("magnit", "магнит", "магнита", "магните"),
    "spar": ("spar", "спар", "eurospar", "евроспар"),
    "pyaterochka": ("pyaterochka", "пятерочка", "пятёрочка", "5ка", "5ka", "x5"),
    "fix_price": ("fix price", "fix_price", "фикс прайс", "fixprice"),
}

SYNONYM_GROUPS = (
    ("карта", "карты", "лояльность", "скидка", "скидочные", "клубная"),
    ("магазин", "магазины", "сеть", "супермаркет"),
    ("корзина", "покупки", "список", "продукты"),
    ("задача", "дело", "todo", "надо", "нужно"),
    ("не нравится", "избегать", "исключить", "не покупать"),
    ("акция", "скидка", "промо", "дешевле"),
)

CARD_MARKERS = ("карта", "карты", "картой", "лояльност", "скидоч")
TASK_MARKERS = ("надо", "нужно", "сделать", "задача", "todo", "напомни")
PREFERENCE_MARKERS = ("люблю", "предпочитаю", "нравится", "не люблю", "не нравится")
EXCLUDE_MARKERS = ("не сравнивать", "исключить", "не ходить", "не покупать в")
DISLIKE_MARKERS = ("не люблю", "не нравится", "избегаю", "избегать", "дорого")
SHOPPING_MARKERS = ("молоко", "яйца", "сахар", "кофе", "бананы", "хлеб", "сыр")
IMPORTANT_MARKERS = ("важно", "важная", "важный", "приоритет", "срочно", "important")
REMINDER_MARKERS = ("напомни", "напомнить", "remind")
URL_RE = re.compile(r"https?://\S+")
DEFAULT_SPACE = "default"
INDEX_DIR = ".assistantbot"
INDEX_FILE = "memory-index.sqlite3"
MAX_CHUNK_LENGTH = 1200


@dataclass(frozen=True)
class MemoryNoteMetadata:
    note_type: str
    tags: list[str]
    reminder_at: datetime | None = None
    status: str = "open"
    space: str = DEFAULT_SPACE
    source_type: str = "manual"
    source_url: str | None = None
    title: str | None = None
    checksum: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class MemorySearchResult:
    path: Path
    score: int
    snippet: str
    note_type: str = "note"
    tags: list[str] = field(default_factory=list)
    space: str = DEFAULT_SPACE
    source_type: str = "manual"
    source_url: str | None = None
    title: str | None = None
    chunk_no: int = 0

    @property
    def citation(self) -> str:
        parts = [self.title or self.path.name]
        if self.source_url:
            parts.append(self.source_url)
        parts.append(f"space:{self.space}")
        return " | ".join(parts)


@dataclass(frozen=True)
class PriceMemoryContext:
    remembered_cards: list[str] = field(default_factory=list)
    disliked_stores: list[str] = field(default_factory=list)
    excluded_stores: list[str] = field(default_factory=list)
    frequent_items: list[str] = field(default_factory=list)
    related_notes: list[MemorySearchResult] = field(default_factory=list)


@dataclass(frozen=True)
class LifestyleMemoryContext:
    preferences: list[MemorySearchResult] = field(default_factory=list)
    decisions: list[MemorySearchResult] = field(default_factory=list)
    shopping_notes: list[MemorySearchResult] = field(default_factory=list)
    frequent_items: list[str] = field(default_factory=list)
    open_tasks: list[MemoryTask] = field(default_factory=list)
    pins: list[MemorySearchResult] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.preferences,
                self.decisions,
                self.shopping_notes,
                self.frequent_items,
                self.open_tasks,
                self.pins,
            )
        )


@dataclass(frozen=True)
class MemoryTask:
    id: str
    path: Path
    snippet: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MemoryReminder:
    id: str
    user_id: int
    path: Path
    due_at: datetime
    snippet: str


@dataclass(frozen=True)
class MemoryCollection:
    name: str
    count: int


@dataclass(frozen=True)
class MemorySpace:
    name: str
    count: int
    active: bool = False


@dataclass(frozen=True)
class MemorySource:
    path: Path
    source_type: str
    title: str
    source_url: str | None = None
    space: str = DEFAULT_SPACE
    checksum: str = ""


class ObsidianMemory:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def remember_user_note(
        self,
        *,
        user_id: int,
        text: str,
        created_at: datetime | None = None,
        note_type: str | None = None,
        extra_tags: list[str] | None = None,
        reminder_at: datetime | None = None,
        space: str | None = None,
        source_type: str = "manual",
        source_url: str | None = None,
        title: str | None = None,
    ) -> Path:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("memory text is empty")

        created = created_at or datetime.now(UTC)
        effective_space = _normalize_space(space or self.get_active_space(user_id))
        checksum = _checksum(clean_text, source_url=source_url)
        duplicate = self._find_duplicate(user_id=user_id, checksum=checksum)
        if duplicate is not None:
            self._index_note(user_id=user_id, path=duplicate)
            return duplicate
        metadata = classify_note(clean_text)
        effective_type = note_type or metadata.note_type
        tags = list(dict.fromkeys([*metadata.tags, *(extra_tags or [])]))
        if effective_type not in tags:
            tags.append(effective_type)
        directory = self._user_notes_dir(user_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = _unique_markdown_path(directory, created.strftime("%Y%m%d-%H%M%S-%f"))
        path.write_text(
            _markdown_note(
                note_type=effective_type,
                user_id=user_id,
                created_at=created,
                tags=tags,
                body=clean_text,
                reminder_at=reminder_at,
                status="open",
                space=effective_space,
                source_type=source_type,
                source_url=source_url,
                title=title,
                checksum=checksum,
                updated_at=created,
            ),
            encoding="utf-8",
        )
        self._append_daily_entry(user_id, created, "Память", clean_text)
        self._append_inbox_entry(user_id, created, clean_text, path)
        if effective_type in {"fact", "preference", "task", "link", "important", "reminder"}:
            self._append_profile_fact(user_id, clean_text)
        self._index_note(user_id=user_id, path=path)
        return path

    def remember_basket(
        self,
        *,
        user_id: int,
        raw_text: str,
        items: list[BasketItemParsed],
        created_at: datetime | None = None,
    ) -> Path:
        clean_text = raw_text.strip()
        if not clean_text:
            raise ValueError("basket text is empty")

        created = created_at or datetime.now(UTC)
        directory = self._user_baskets_dir(user_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = _unique_markdown_path(directory, created.strftime("%Y%m%d-%H%M%S-%f"))
        body_lines = ["Корзина:", ""]
        body_lines.extend(f"- {item.raw_text}" for item in items)
        body = "\n".join(body_lines)
        path.write_text(
            _markdown_note(
                note_type="basket",
                user_id=user_id,
                created_at=created,
                tags=["pricebot", "basket", "shopping"],
                body=body,
            ),
            encoding="utf-8",
        )
        self._append_daily_entry(user_id, created, "Корзина", clean_text)
        return path

    def search_user_notes(
        self,
        *,
        user_id: int,
        query: str,
        limit: int = 5,
        space: str | None = None,
    ) -> list[MemorySearchResult]:
        tokens = _tokens(query)
        expanded = _expand_terms(tokens)
        if not expanded:
            return []

        indexed_results = self._search_index(
            user_id=user_id,
            query=query,
            limit=limit,
            space=space,
        )
        if indexed_results:
            return indexed_results

        results: list[MemorySearchResult] = []
        for path, text in self._iter_user_markdown(user_id):
            metadata = _parse_frontmatter(text)
            if space is not None and metadata.space != _normalize_space(space):
                continue
            body = _strip_frontmatter(text)
            searchable = " ".join([body, metadata.note_type, " ".join(metadata.tags)]).lower()
            score = _score_text(searchable, tokens, expanded)
            if score <= 0:
                continue
            results.append(
                MemorySearchResult(
                    path=path,
                    score=score,
                    snippet=_snippet(text, expanded),
                    note_type=metadata.note_type,
                    tags=metadata.tags,
                    space=metadata.space,
                    source_type=metadata.source_type,
                    source_url=metadata.source_url,
                    title=metadata.title,
                )
            )
        results.sort(key=lambda result: (-result.score, str(result.path)))
        return results[:limit]

    def ask_user_memory(self, *, user_id: int, question: str) -> str:
        results = self.search_user_notes(user_id=user_id, query=question, limit=5)
        if not results:
            return "В памяти пока нет подходящих заметок."

        lines = ["По памяти нашел:"]
        for result in results:
            lines.append(f"- {result.snippet}")
        return "\n".join(lines)

    def today_digest(self, *, user_id: int, created_at: datetime | None = None) -> str:
        current = created_at or datetime.now(UTC)
        path = self._user_daily_dir(user_id) / f"{current.strftime('%Y-%m-%d')}.md"
        if not path.exists():
            return "За сегодня в памяти пока ничего нет."
        body = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not body:
            return "За сегодня в памяти пока ничего нет."
        return body[:3900]

    def list_open_tasks(self, *, user_id: int, limit: int = 10) -> list[MemoryTask]:
        tasks: list[MemoryTask] = []
        for path, text in self._iter_user_notes(user_id):
            metadata = _parse_frontmatter(text)
            if metadata.note_type != "task" and "task" not in metadata.tags:
                continue
            if metadata.status == "done":
                continue
            body = _strip_frontmatter(text).strip()
            if _looks_completed(body):
                continue
            tasks.append(
                MemoryTask(
                    id=path.stem,
                    path=path,
                    snippet=_snippet(text, _tokens(body)[:3]),
                    tags=metadata.tags,
                )
            )
        tasks.sort(key=lambda task: str(task.path), reverse=True)
        return tasks[:limit]

    def related_context(
        self,
        *,
        user_id: int,
        text: str,
        limit: int = 5,
        space: str | None = None,
    ) -> list[MemorySearchResult]:
        return self.search_user_notes(user_id=user_id, query=text, limit=limit, space=space)

    def recent_notes(
        self,
        *,
        user_id: int,
        limit: int = 10,
        space: str | None = None,
    ) -> list[MemorySearchResult]:
        notes: list[MemorySearchResult] = []
        for path, text in self._iter_user_notes(user_id):
            metadata = _parse_frontmatter(text)
            if space is not None and metadata.space != _normalize_space(space):
                continue
            body = _strip_frontmatter(text)
            notes.append(
                MemorySearchResult(
                    path=path,
                    score=0,
                    snippet=_snippet(body, _tokens(body)[:3]),
                    note_type=metadata.note_type,
                    tags=metadata.tags,
                    space=metadata.space,
                    source_type=metadata.source_type,
                    source_url=metadata.source_url,
                    title=metadata.title,
                )
            )
        notes.sort(key=lambda note: str(note.path), reverse=True)
        return notes[:limit]

    def list_spaces(self, *, user_id: int) -> list[MemorySpace]:
        active = self.get_active_space(user_id)
        counts: Counter[str] = Counter()
        for _, text in self._iter_user_markdown(user_id):
            counts[_parse_frontmatter(text).space] += 1
        if active not in counts:
            counts[active] = 0
        return [
            MemorySpace(name=name, count=count, active=name == active)
            for name, count in sorted(counts.items(), key=lambda item: (item[0] != active, item[0]))
        ]

    def get_active_space(self, user_id: int) -> str:
        path = self._active_space_path(user_id)
        if not path.exists():
            return DEFAULT_SPACE
        return _normalize_space(path.read_text(encoding="utf-8", errors="ignore"))

    def set_active_space(self, *, user_id: int, space: str) -> str:
        normalized = _normalize_space(space)
        path = self._active_space_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(normalized, encoding="utf-8")
        return normalized

    def list_collections(self, *, user_id: int) -> list[MemoryCollection]:
        counts: Counter[str] = Counter()
        for _, text in self._iter_user_markdown(user_id):
            metadata = _parse_frontmatter(text)
            names = {metadata.note_type}
            for tag in metadata.tags:
                if tag not in {"pricebot", "memory"}:
                    names.add(tag)
            for name in names:
                counts[name] += 1
        return [
            MemoryCollection(name=name, count=count)
            for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def collection_notes(
        self,
        *,
        user_id: int,
        collection: str,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        normalized = _normalize_text(collection.strip())
        notes: list[MemorySearchResult] = []
        for path, text in self._iter_user_markdown(user_id):
            metadata = _parse_frontmatter(text)
            names = {_normalize_text(metadata.note_type), *map(_normalize_text, metadata.tags)}
            if normalized not in names:
                continue
            body = _strip_frontmatter(text)
            notes.append(
                MemorySearchResult(
                    path=path,
                    score=0,
                    snippet=_snippet(body, _tokens(body)[:3]),
                    note_type=metadata.note_type,
                    tags=metadata.tags,
                    space=metadata.space,
                    source_type=metadata.source_type,
                    source_url=metadata.source_url,
                    title=metadata.title,
                )
            )
        notes.sort(key=lambda note: str(note.path), reverse=True)
        return notes[:limit]

    def list_pins(self, *, user_id: int, limit: int = 10) -> list[MemorySearchResult]:
        return self.collection_notes(user_id=user_id, collection="important", limit=limit)

    def list_sources(self, *, user_id: int, limit: int = 20) -> list[MemorySource]:
        sources: list[MemorySource] = []
        for path, text in self._iter_user_notes(user_id):
            metadata = _parse_frontmatter(text)
            sources.append(
                MemorySource(
                    path=path,
                    source_type=metadata.source_type,
                    title=metadata.title or path.name,
                    source_url=metadata.source_url,
                    space=metadata.space,
                    checksum=metadata.checksum,
                )
            )
        sources.sort(key=lambda source: str(source.path), reverse=True)
        return sources[:limit]

    def filtered_search(
        self,
        *,
        user_id: int,
        query: str,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        clean_query, filters = _parse_search_filters(query)
        candidates = (
            self.search_user_notes(user_id=user_id, query=clean_query, limit=limit * 4)
            if clean_query
            else self.recent_notes(user_id=user_id, limit=limit * 4)
        )
        results = []
        for result in candidates:
            text = result.path.read_text(encoding="utf-8", errors="ignore")
            metadata = _parse_frontmatter(text)
            if filters.get("type") and metadata.note_type != filters["type"]:
                continue
            if filters.get("tag") and filters["tag"] not in metadata.tags:
                continue
            if filters.get("space") and metadata.space != _normalize_space(filters["space"]):
                continue
            after = filters.get("after")
            if after and (
                metadata.created_at is None or metadata.created_at.date().isoformat() < after
            ):
                continue
            results.append(result)
        return results[:limit]

    def inbox_review(self, *, user_id: int, limit: int = 10) -> list[MemorySearchResult]:
        return [
            note
            for note in self.recent_notes(user_id=user_id, limit=limit * 3)
            if note.note_type == "fact" and not {"task", "person", "decision", "journal", "link"}
            & set(note.tags)
        ][:limit]

    def add_note_tag(self, *, user_id: int, note_id: str, tag: str) -> bool:
        path = self._user_notes_dir(user_id) / f"{note_id}.md"
        clean_tag = _normalize_space(tag)
        if not path.exists() or not clean_tag:
            return False
        text = path.read_text(encoding="utf-8", errors="ignore")
        metadata = _parse_frontmatter(text)
        tags = list(dict.fromkeys([*metadata.tags, clean_tag]))
        self._set_frontmatter_value(path, key="tags", value=f"[{', '.join(tags)}]")
        self._index_note(user_id=user_id, path=path)
        return True

    def create_task(
        self,
        *,
        user_id: int,
        text: str,
        created_at: datetime | None = None,
        space: str | None = None,
    ) -> Path:
        return self.remember_user_note(
            user_id=user_id,
            text=text,
            created_at=created_at,
            note_type="task",
            extra_tags=["task"],
            space=space,
        )

    def remember_preference(
        self,
        *,
        user_id: int,
        text: str,
        created_at: datetime | None = None,
        space: str | None = None,
    ) -> Path:
        return self.remember_user_note(
            user_id=user_id,
            text=text,
            created_at=created_at,
            note_type="preference",
            extra_tags=["preference", *_lifestyle_tags(text)],
            space=space,
        )

    def create_journal_entry(
        self,
        *,
        user_id: int,
        text: str,
        created_at: datetime | None = None,
        space: str | None = None,
    ) -> Path:
        return self.remember_user_note(
            user_id=user_id,
            text=text,
            created_at=created_at,
            note_type="journal",
            extra_tags=["journal"],
            space=space,
        )

    def remember_person_note(
        self,
        *,
        user_id: int,
        person_name: str,
        text: str,
        created_at: datetime | None = None,
        space: str | None = None,
    ) -> Path:
        clean_name = " ".join(person_name.strip().split())
        clean_text = text.strip()
        if not clean_name:
            raise ValueError("person name is empty")
        if not clean_text:
            raise ValueError("person note is empty")
        return self.remember_user_note(
            user_id=user_id,
            text=f"Person: {clean_name}\n\n{clean_text}",
            created_at=created_at,
            note_type="person",
            extra_tags=["person", _normalize_space(clean_name)],
            space=space,
            title=f"Person: {clean_name}",
        )

    def person_notes(
        self,
        *,
        user_id: int,
        person_name: str,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        clean_name = " ".join(person_name.strip().split())
        if not clean_name:
            return []
        return self.search_user_notes(user_id=user_id, query=clean_name, limit=limit)

    def create_decision_note(
        self,
        *,
        user_id: int,
        prompt: str,
        created_at: datetime | None = None,
        space: str | None = None,
    ) -> tuple[Path, list[MemorySearchResult]]:
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("decision prompt is empty")
        related = self.related_context(user_id=user_id, text=clean_prompt, limit=3, space=space)
        body = _decision_note_body(clean_prompt, related)
        path = self.remember_user_note(
            user_id=user_id,
            text=body,
            created_at=created_at,
            note_type="decision",
            extra_tags=["decision"],
            space=space,
            title=clean_prompt[:80],
        )
        return path, related

    def period_digest(
        self,
        *,
        user_id: int,
        days: int = 7,
        created_at: datetime | None = None,
    ) -> str:
        safe_days = max(1, min(days, 90))
        current = (created_at or datetime.now(UTC)).astimezone(UTC)
        start = current - timedelta(days=safe_days)
        notes: list[tuple[Path, str, MemoryNoteMetadata]] = []
        for path, text in self._iter_user_notes(user_id):
            metadata = _parse_frontmatter(text)
            if metadata.created_at is None or metadata.created_at < start:
                continue
            notes.append((path, text, metadata))
        if not notes:
            return f"За последние {safe_days} дн. в памяти нет новых заметок."

        type_counts: Counter[str] = Counter(metadata.note_type for _, _, metadata in notes)
        tag_counts: Counter[str] = Counter(
            tag
            for _, _, metadata in notes
            for tag in metadata.tags
            if tag not in {"pricebot", "memory"}
        )
        open_tasks = self.list_open_tasks(user_id=user_id, limit=5)
        important = [
            _snippet(text, _tokens(_strip_frontmatter(text))[:3])
            for _, text, metadata in notes
            if metadata.note_type == "important" or "important" in metadata.tags
        ][:5]
        recent = [
            _snippet(text, _tokens(_strip_frontmatter(text))[:3])
            for _, text, _ in sorted(notes, key=lambda item: str(item[0]), reverse=True)[:5]
        ]

        lines = [
            f"Дайджест за {safe_days} дн.",
            f"Заметок: {len(notes)}",
            "Типы: " + _format_counter(type_counts),
        ]
        if tag_counts:
            lines.append("Темы: " + _format_counter(tag_counts, limit=8))
        if open_tasks:
            lines.append("")
            lines.append("Открытые задачи:")
            lines.extend(f"- {task.snippet}" for task in open_tasks)
        if important:
            lines.append("")
            lines.append("Важное:")
            lines.extend(f"- {snippet}" for snippet in important)
        lines.append("")
        lines.append("Последние заметки:")
        lines.extend(f"- {snippet}" for snippet in recent)
        return "\n".join(lines)[:3900]

    def complete_task(
        self,
        *,
        user_id: int,
        task_id: str,
        completed_at: datetime | None = None,
    ) -> bool:
        path = self._user_notes_dir(user_id) / f"{task_id}.md"
        if not path.exists():
            return False
        text = path.read_text(encoding="utf-8", errors="ignore")
        metadata = _parse_frontmatter(text)
        if metadata.note_type != "task" and "task" not in metadata.tags:
            return False
        if metadata.status == "done":
            return False
        self._set_frontmatter_value(path, key="status", value="done")
        self._index_note(user_id=user_id, path=path)
        done_at = completed_at or datetime.now(UTC)
        with path.open("a", encoding="utf-8") as file:
            file.write(f"\nDone: {done_at.isoformat()}\n")
        return True

    def create_reminder(
        self,
        *,
        user_id: int,
        text: str,
        due_at: datetime,
        created_at: datetime | None = None,
        space: str | None = None,
    ) -> Path:
        return self.remember_user_note(
            user_id=user_id,
            text=text,
            created_at=created_at,
            note_type="reminder",
            extra_tags=["reminder", "task"],
            reminder_at=due_at.astimezone(UTC),
            space=space,
            source_type="reminder",
        )

    def list_reminders(self, *, user_id: int, limit: int = 10) -> list[MemoryReminder]:
        reminders = [reminder for reminder in self.iter_reminders() if reminder.user_id == user_id]
        reminders.sort(key=lambda reminder: reminder.due_at)
        return reminders[:limit]

    def due_reminders(self, *, now: datetime | None = None) -> list[MemoryReminder]:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        return [reminder for reminder in self.iter_reminders() if reminder.due_at <= current]

    def iter_reminders(self) -> list[MemoryReminder]:
        reminders: list[MemoryReminder] = []
        users_dir = self.vault_path / "users"
        if not users_dir.exists():
            return []
        for user_dir in users_dir.iterdir():
            if not user_dir.is_dir() or not user_dir.name.isdigit():
                continue
            user_id = int(user_dir.name)
            for path in (user_dir / "notes").glob("*.md"):
                text = path.read_text(encoding="utf-8", errors="ignore")
                metadata = _parse_frontmatter(text)
                if metadata.reminder_at is None or metadata.status == "done":
                    continue
                reminders.append(
                    MemoryReminder(
                        id=path.stem,
                        user_id=user_id,
                        path=path,
                        due_at=metadata.reminder_at,
                        snippet=_snippet(text, _tokens(_strip_frontmatter(text))[:3]),
                    )
                )
        return reminders

    def mark_reminder_sent(self, path: Path) -> None:
        self._set_frontmatter_value(path, key="status", value="done")
        user_id = _user_id_from_path(path)
        if user_id is not None:
            self._index_note(user_id=user_id, path=path)

    def delete_note(self, *, user_id: int, note_id: str) -> bool:
        path = self._user_notes_dir(user_id) / f"{note_id}.md"
        if not path.exists():
            return False
        path.unlink()
        self._delete_from_index(path)
        return True

    def rebuild_user_index(self, *, user_id: int) -> int:
        count = 0
        for path, _ in self._iter_user_notes(user_id):
            self._index_note(user_id=user_id, path=path)
            count += 1
        return count

    def _find_duplicate(self, *, user_id: int, checksum: str) -> Path | None:
        if not checksum:
            return None
        for path, text in self._iter_user_notes(user_id):
            metadata = _parse_frontmatter(text)
            if metadata.checksum == checksum:
                return path
        return None

    def _index_note(self, *, user_id: int, path: Path) -> None:
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8", errors="ignore")
        metadata = _parse_frontmatter(text)
        body = _strip_frontmatter(text).strip()
        if not body:
            return
        try:
            with self._connect_index() as connection:
                self._prepare_index(connection)
                self._delete_from_index(path, connection=connection)
                for chunk_no, chunk in enumerate(_chunks(body), start=1):
                    connection.execute(
                        """
                        insert into memory_fts(
                            path, chunk_no, user_id, space, note_type, tags, source_type,
                            source_url, title, status, body
                        )
                        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(path),
                            chunk_no,
                            user_id,
                            metadata.space,
                            metadata.note_type,
                            ",".join(metadata.tags),
                            metadata.source_type,
                            metadata.source_url or "",
                            metadata.title or path.name,
                            metadata.status,
                            chunk,
                        ),
                    )
                connection.execute(
                    """
                    insert or replace into memory_sources(
                        path, user_id, space, note_type, source_type, source_url, title,
                        checksum, status, created_at, updated_at
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(path),
                        user_id,
                        metadata.space,
                        metadata.note_type,
                        metadata.source_type,
                        metadata.source_url,
                        metadata.title or path.name,
                        metadata.checksum,
                        metadata.status,
                        metadata.created_at.isoformat() if metadata.created_at else "",
                        metadata.updated_at.isoformat() if metadata.updated_at else "",
                    ),
                )
        except sqlite3.Error:
            return

    def _search_index(
        self,
        *,
        user_id: int,
        query: str,
        limit: int,
        space: str | None,
    ) -> list[MemorySearchResult]:
        self.rebuild_user_index(user_id=user_id)
        fts_query = _fts_query(query)
        if not fts_query:
            return []
        try:
            with self._connect_index() as connection:
                self._prepare_index(connection)
                params: list[object] = [fts_query, user_id]
                space_filter = ""
                if space is not None:
                    space_filter = " and space = ?"
                    params.append(_normalize_space(space))
                params.append(limit)
                rows = connection.execute(
                    f"""
                    select path, bm25(memory_fts) as rank,
                           snippet(memory_fts, 10, '', '', '...', 24),
                           note_type, tags, space, source_type, source_url, title, chunk_no
                    from memory_fts
                    where memory_fts match ? and user_id = ?{space_filter}
                    order by rank
                    limit ?
                    """,
                    params,
                ).fetchall()
        except sqlite3.Error:
            return []
        results: list[MemorySearchResult] = []
        for row in rows:
            path = Path(str(row[0]))
            tags = [tag for tag in str(row[4]).split(",") if tag]
            results.append(
                MemorySearchResult(
                    path=path,
                    score=max(1, int(abs(float(row[1])) * 1000)),
                    snippet=str(row[2]).strip(),
                    note_type=str(row[3]),
                    tags=tags,
                    space=str(row[5]),
                    source_type=str(row[6]),
                    source_url=str(row[7]) or None,
                    title=str(row[8]) or None,
                    chunk_no=int(row[9]),
                )
            )
        return results

    def _delete_from_index(
        self,
        path: Path,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        own_connection = connection is None
        try:
            active_connection = connection or self._connect_index()
            self._prepare_index(active_connection)
            active_connection.execute("delete from memory_fts where path = ?", (str(path),))
            active_connection.execute("delete from memory_sources where path = ?", (str(path),))
            if own_connection:
                active_connection.commit()
        except sqlite3.Error:
            return
        finally:
            if own_connection and "active_connection" in locals():
                active_connection.close()

    def _connect_index(self) -> sqlite3.Connection:
        directory = self.vault_path / INDEX_DIR
        directory.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(directory / INDEX_FILE)

    def _prepare_index(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            create virtual table if not exists memory_fts using fts5(
                path unindexed,
                chunk_no unindexed,
                user_id unindexed,
                space unindexed,
                note_type unindexed,
                tags,
                source_type unindexed,
                source_url unindexed,
                title,
                status unindexed,
                body
            )
            """
        )
        connection.execute(
            """
            create table if not exists memory_sources (
                path text primary key,
                user_id integer not null,
                space text not null,
                note_type text not null,
                source_type text not null,
                source_url text,
                title text,
                checksum text,
                status text,
                created_at text,
                updated_at text
            )
            """
        )

    def _set_frontmatter_value(self, path: Path, *, key: str, value: str) -> None:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            path.write_text(f"---\n{key}: {value}\n---\n\n{text}", encoding="utf-8")
            return
        parts = text.split("---", 2)
        if len(parts) < 3:
            path.write_text(f"---\n{key}: {value}\n---\n\n{text}", encoding="utf-8")
            return
        frontmatter = parts[1].splitlines()
        updated = False
        for index, line in enumerate(frontmatter):
            if line.startswith(f"{key}:"):
                frontmatter[index] = f"{key}: {value}"
                updated = True
                break
        if not updated:
            frontmatter.append(f"{key}: {value}")
        body = parts[2]
        frontmatter_text = "\n".join(frontmatter)
        path.write_text(f"---\n{frontmatter_text}\n---{body}", encoding="utf-8")

    def build_price_context(
        self,
        *,
        user_id: int,
        items: list[BasketItemParsed],
    ) -> PriceMemoryContext:
        texts = [text for _, text in self._iter_user_notes(user_id)]
        bodies = [_strip_frontmatter(text).lower() for text in texts]
        item_query = " ".join(item.raw_text for item in items)
        item_names = [item.name.lower() for item in items]
        return PriceMemoryContext(
            remembered_cards=_stores_matching_in_notes(bodies, CARD_MARKERS),
            disliked_stores=_stores_matching_in_notes(bodies, DISLIKE_MARKERS),
            excluded_stores=_stores_matching_in_notes(bodies, EXCLUDE_MARKERS),
            frequent_items=self._frequent_items_for(user_id, item_names),
            related_notes=self.search_user_notes(user_id=user_id, query=item_query, limit=2),
        )

    def settings_with_memory(self, settings: Any, context: PriceMemoryContext) -> SimpleNamespace:
        enabled = list(getattr(settings, "enabled_store_slugs", []) or [])
        excluded = set(context.excluded_stores)
        if enabled and excluded:
            enabled = [slug for slug in enabled if slug not in excluded]

        values: dict[str, object] = {
            "enabled_store_slugs": enabled,
            "comparison_mode": getattr(settings, "comparison_mode", "mixed"),
        }
        for slug in STORE_LABELS:
            attr = f"has_{slug}_card"
            values[attr] = bool(getattr(settings, attr, False)) or slug in context.remembered_cards
        return SimpleNamespace(**values)

    def format_price_heads_up(
        self,
        *,
        context: PriceMemoryContext,
        original_settings: Any,
    ) -> str:
        lines: list[str] = []
        remembered_cards = [
            slug
            for slug in context.remembered_cards
            if not bool(getattr(original_settings, f"has_{slug}_card", False))
        ]
        if remembered_cards:
            cards = ", ".join(STORE_LABELS[slug] for slug in remembered_cards)
            lines.append(f"Нашел в памяти карты лояльности: {cards}. Учитываю цены по карте.")
        if context.excluded_stores:
            stores = ", ".join(STORE_LABELS[slug] for slug in context.excluded_stores)
            lines.append(f"По памяти исключаю магазины: {stores}.")
        elif context.disliked_stores:
            stores = ", ".join(STORE_LABELS[slug] for slug in context.disliked_stores)
            lines.append(f"В памяти есть осторожность по магазинам: {stores}.")
        if context.frequent_items:
            lines.append(f"Частые товары из прошлых корзин: {', '.join(context.frequent_items)}.")
        if context.related_notes:
            lines.append(f"Связанная заметка: {context.related_notes[0].snippet}")
        return "\n".join(["Память:"] + lines) if lines else ""

    def build_lifestyle_context(
        self,
        *,
        user_id: int,
        limit: int = 5,
    ) -> LifestyleMemoryContext:
        return LifestyleMemoryContext(
            preferences=self.collection_notes(
                user_id=user_id,
                collection="preference",
                limit=limit,
            ),
            decisions=self.collection_notes(
                user_id=user_id,
                collection="decision",
                limit=limit,
            ),
            shopping_notes=self.collection_notes(
                user_id=user_id,
                collection="shopping",
                limit=limit,
            ),
            frequent_items=self.frequent_basket_items(user_id=user_id, limit=limit),
            open_tasks=self.list_open_tasks(user_id=user_id, limit=limit),
            pins=self.list_pins(user_id=user_id, limit=limit),
        )

    def lifestyle_focus_notes(
        self,
        *,
        user_id: int,
        limit: int = 5,
    ) -> list[str]:
        context = self.build_lifestyle_context(user_id=user_id, limit=limit)
        notes: list[str] = []
        if context.pins:
            notes.append(f"Важное: {context.pins[0].snippet}")
        if context.preferences:
            notes.append(f"Предпочтение: {context.preferences[0].snippet}")
        if context.decisions:
            notes.append(f"Последнее решение: {context.decisions[0].snippet}")
        if context.frequent_items:
            notes.append("Частые покупки: " + ", ".join(context.frequent_items[:5]))
        if context.open_tasks:
            notes.append(f"Открытая задача: {context.open_tasks[0].snippet}")
        return notes[:limit]

    def format_lifestyle_context(
        self,
        *,
        user_id: int,
        limit: int = 5,
    ) -> str:
        context = self.build_lifestyle_context(user_id=user_id, limit=limit)
        if context.is_empty:
            return "Lifestyle context пока пуст. Добавь предпочтения через /preference."
        lines = ["Lifestyle context"]
        if context.preferences:
            lines.append("")
            lines.append("Предпочтения:")
            lines.extend(f"- {note.snippet}" for note in context.preferences[:limit])
        if context.decisions:
            lines.append("")
            lines.append("Решения:")
            lines.extend(f"- {note.snippet}" for note in context.decisions[:limit])
        if context.frequent_items:
            lines.append("")
            lines.append("Частые покупки: " + ", ".join(context.frequent_items[:limit]))
        if context.open_tasks:
            lines.append("")
            lines.append("Открытые задачи:")
            lines.extend(f"- {task.snippet}" for task in context.open_tasks[:limit])
        if context.pins:
            lines.append("")
            lines.append("Важное:")
            lines.extend(f"- {pin.snippet}" for pin in context.pins[:limit])
        if context.shopping_notes:
            lines.append("")
            lines.append("Покупки и быт:")
            lines.extend(f"- {note.snippet}" for note in context.shopping_notes[:limit])
        return "\n".join(lines)[:3900]

    def frequent_basket_items(self, *, user_id: int, limit: int = 5) -> list[str]:
        counts = self._basket_item_counts(user_id)
        return [item for item, _ in counts.most_common(limit)]

    def _append_daily_entry(
        self,
        user_id: int,
        created_at: datetime,
        title: str,
        text: str,
    ) -> None:
        directory = self._user_daily_dir(user_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{created_at.strftime('%Y-%m-%d')}.md"
        entry = f"\n### {created_at.strftime('%H:%M')} {title}\n\n{text.strip()}\n"
        if not path.exists():
            path.write_text(f"# {created_at.strftime('%Y-%m-%d')}\n{entry}", encoding="utf-8")
            return
        with path.open("a", encoding="utf-8") as file:
            file.write(entry)

    def _append_inbox_entry(
        self,
        user_id: int,
        created_at: datetime,
        text: str,
        note_path: Path,
    ) -> None:
        directory = self.vault_path / "inbox"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{created_at.strftime('%Y-%m-%d')}.md"
        relative = note_path.relative_to(self.vault_path).as_posix()
        entry = f"- {created_at.strftime('%H:%M')} user:{user_id} [[{relative}]] {text.strip()}\n"
        if not path.exists():
            heading = f"# Inbox {created_at.strftime('%Y-%m-%d')}"
            path.write_text(f"{heading}\n\n{entry}", encoding="utf-8")
            return
        with path.open("a", encoding="utf-8") as file:
            file.write(entry)

    def _append_profile_fact(self, user_id: int, text: str) -> None:
        directory = self._user_dir(user_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "profile.md"
        fact = text.strip()
        line = f"- {fact}\n"
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if line in existing:
                return
            with path.open("a", encoding="utf-8") as file:
                file.write(line)
            return
        path.write_text(f"# User {user_id}\n\n## Facts\n\n{line}", encoding="utf-8")

    def _frequent_items_for(
        self,
        user_id: int,
        item_names: list[str],
        *,
        min_count: int = 2,
    ) -> list[str]:
        counts = self._basket_item_counts(user_id)
        frequent: list[str] = []
        for item_name in item_names:
            for saved, count in counts.items():
                if count >= min_count and item_name and item_name in saved:
                    frequent.append(item_name)
                    break
        return list(dict.fromkeys(frequent))[:5]

    def _basket_item_counts(self, user_id: int) -> Counter[str]:
        counts: Counter[str] = Counter()
        for path in self._user_baskets_dir(user_id).glob("*.md"):
            body = _strip_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
            for line in body.splitlines():
                if line.startswith("- "):
                    counts[_basket_item_name(line[2:].strip())] += 1
        return counts

    def _iter_user_markdown(self, user_id: int) -> list[tuple[Path, str]]:
        directory = self._user_dir(user_id)
        if not directory.exists():
            return []
        return [
            (path, path.read_text(encoding="utf-8", errors="ignore"))
            for path in directory.rglob("*.md")
        ]

    def _iter_user_notes(self, user_id: int) -> list[tuple[Path, str]]:
        directory = self._user_notes_dir(user_id)
        if not directory.exists():
            return []
        return [
            (path, path.read_text(encoding="utf-8", errors="ignore"))
            for path in directory.glob("*.md")
        ]

    def _user_dir(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id)

    def _user_notes_dir(self, user_id: int) -> Path:
        return self._user_dir(user_id) / "notes"

    def _user_baskets_dir(self, user_id: int) -> Path:
        return self._user_dir(user_id) / "baskets"

    def _user_daily_dir(self, user_id: int) -> Path:
        return self._user_dir(user_id) / "daily"

    def _active_space_path(self, user_id: int) -> Path:
        return self._user_dir(user_id) / "active-space.txt"


def classify_note(text: str) -> MemoryNoteMetadata:
    lowered = _normalize_text(text)
    tags = ["pricebot", "memory"]
    note_type = "fact"
    important_markers = IMPORTANT_MARKERS + (
        "важно",
        "важная",
        "важный",
        "приоритет",
        "срочно",
    )
    reminder_markers = REMINDER_MARKERS + ("напомни", "напомнить", "напоминание")
    if URL_RE.search(text):
        note_type = "link"
        tags.append("link")
    if _contains_any(lowered, TASK_MARKERS):
        note_type = "task"
        tags.append("task")
    if _contains_any(lowered, PREFERENCE_MARKERS) or _contains_any(lowered, CARD_MARKERS):
        note_type = "preference"
        tags.append("preference")
    if _contains_any(lowered, CARD_MARKERS):
        tags.append("loyalty")
    if _contains_any(lowered, SHOPPING_MARKERS):
        tags.append("shopping")
    if _contains_any(lowered, important_markers):
        note_type = "important"
        tags.append("important")
    if _contains_any(lowered, reminder_markers):
        note_type = "reminder"
        tags.extend(["reminder", "task"])
    for slug, aliases in STORE_ALIASES.items():
        if _contains_any(lowered, aliases):
            tags.append(slug)
    return MemoryNoteMetadata(note_type=note_type, tags=list(dict.fromkeys(tags)))


def _markdown_note(
    *,
    note_type: str,
    user_id: int,
    created_at: datetime,
    tags: list[str],
    body: str,
    reminder_at: datetime | None = None,
    status: str = "open",
    space: str = DEFAULT_SPACE,
    source_type: str = "manual",
    source_url: str | None = None,
    title: str | None = None,
    checksum: str = "",
    updated_at: datetime | None = None,
) -> str:
    tags_text = ", ".join(tags)
    lines = [
        "---",
        f"type: {note_type}",
        f"user_id: {user_id}",
        f"created_at: {created_at.isoformat()}",
        f"updated_at: {(updated_at or created_at).isoformat()}",
        f"tags: [{tags_text}]",
        f"status: {status}",
        f"space: {space}",
        f"source_type: {source_type}",
        f"checksum: {checksum}",
    ]
    if title:
        lines.append(f"title: {_frontmatter_value(title)}")
    if source_url:
        lines.append(f"source_url: {_frontmatter_value(source_url)}")
    if reminder_at is not None:
        lines.append(f"reminder_at: {reminder_at.astimezone(UTC).isoformat()}")
    lines.extend(["---", "", body.strip(), ""])
    return "\n".join(lines)


def _parse_frontmatter(text: str) -> MemoryNoteMetadata:
    if not text.startswith("---"):
        return MemoryNoteMetadata(note_type="note", tags=[])
    parts = text.split("---", 2)
    if len(parts) < 3:
        return MemoryNoteMetadata(note_type="note", tags=[])
    note_type = "note"
    tags: list[str] = []
    reminder_at: datetime | None = None
    status = "open"
    space = DEFAULT_SPACE
    source_type = "manual"
    source_url: str | None = None
    title: str | None = None
    checksum = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    for line in parts[1].splitlines():
        if line.startswith("type:"):
            note_type = line.partition(":")[2].strip() or "note"
        if line.startswith("created_at:"):
            created_at = _parse_datetime(line.partition(":")[2].strip())
        if line.startswith("updated_at:"):
            updated_at = _parse_datetime(line.partition(":")[2].strip())
        if line.startswith("tags:"):
            raw = line.partition(":")[2].strip().strip("[]")
            tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
        if line.startswith("reminder_at:"):
            raw_reminder_at = line.partition(":")[2].strip()
            try:
                reminder_at = datetime.fromisoformat(raw_reminder_at).astimezone(UTC)
            except ValueError:
                reminder_at = None
        if line.startswith("status:"):
            status = line.partition(":")[2].strip() or "open"
        if line.startswith("space:"):
            space = _normalize_space(line.partition(":")[2].strip())
        if line.startswith("source_type:"):
            source_type = line.partition(":")[2].strip() or "manual"
        if line.startswith("source_url:"):
            source_url = _unquote_frontmatter_value(line.partition(":")[2].strip()) or None
        if line.startswith("title:"):
            title = _unquote_frontmatter_value(line.partition(":")[2].strip()) or None
        if line.startswith("checksum:"):
            checksum = line.partition(":")[2].strip()
    return MemoryNoteMetadata(
        note_type=note_type,
        tags=tags,
        reminder_at=reminder_at,
        status=status,
        space=space,
        source_type=source_type,
        source_url=source_url,
        title=title,
        checksum=checksum,
        created_at=created_at,
        updated_at=updated_at,
    )


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[\wа-яА-ЯёЁ]+", _normalize_text(text))
        if len(token) > 1
    ]


def _expand_terms(tokens: list[str]) -> list[str]:
    expanded = set(tokens)
    for token in tokens:
        stem = _soft_stem(token)
        if stem:
            expanded.add(stem)
        for group in SYNONYM_GROUPS:
            normalized_group = {_normalize_text(item) for item in group}
            if token in normalized_group:
                expanded.update(normalized_group)
    for slug, aliases in STORE_ALIASES.items():
        normalized_aliases = {_normalize_text(alias) for alias in aliases}
        if expanded & normalized_aliases:
            expanded.add(slug)
            expanded.update(normalized_aliases)
    return list(expanded)


def _score_text(text: str, tokens: list[str], expanded: list[str]) -> int:
    normalized = _normalize_text(text)
    score = 0
    for token in tokens:
        score += normalized.count(token) * 3
    for token in expanded:
        if token not in tokens:
            score += normalized.count(token)
    return score


def _stores_matching(text: str, markers: tuple[str, ...]) -> list[str]:
    matched: list[str] = []
    normalized = _normalize_text(text)
    if not _contains_any(normalized, markers):
        return []
    for slug, aliases in STORE_ALIASES.items():
        if _contains_any(normalized, aliases):
            matched.append(slug)
    return matched


def _stores_matching_in_notes(texts: list[str], markers: tuple[str, ...]) -> list[str]:
    matched: list[str] = []
    for text in texts:
        matched.extend(_stores_matching(text, markers))
    return list(dict.fromkeys(matched))


def _lifestyle_tags(text: str) -> list[str]:
    normalized = _normalize_text(text)
    tags: list[str] = []
    if _contains_any(normalized, SHOPPING_MARKERS):
        tags.append("shopping")
    if any(word in normalized for word in ("бюджет", "траты", "расход", "чек")):
        tags.append("budget")
    if any(word in normalized for word in ("склад", "pantry", "дома", "законч")):
        tags.append("pantry")
    for slug, aliases in STORE_ALIASES.items():
        if _contains_any(normalized, aliases):
            tags.append(slug)
    return list(dict.fromkeys(tags))


def _basket_item_name(text: str) -> str:
    clean = _normalize_text(text)
    clean = re.sub(r"^\d+(?:[.,]\d+)?x\s+", "", clean)
    clean = re.sub(r"\s+x\d+(?:[.,]\d+)?$", "", clean)
    clean = re.sub(r"\b\d+(?:[.,]\d+)?\s*(кг|г|гр|л|мл|шт|%)?\b", " ", clean)
    tokens = [
        token
        for token in clean.split()
        if token not in {"c0", "c1", "с0", "с1", "уп", "пачка"}
    ]
    return " ".join(tokens).strip() or clean.strip()


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    normalized = _normalize_text(text)
    return any(_normalize_text(marker) in normalized for marker in markers)


def _snippet(text: str, tokens: list[str], max_length: int = 180) -> str:
    body = _strip_frontmatter(text).strip()
    lowered = _normalize_text(body)
    start = 0
    for token in tokens:
        index = lowered.find(token)
        if index >= 0:
            start = max(0, index - 40)
            break
    snippet = " ".join(body[start : start + max_length].split())
    if start > 0:
        snippet = f"...{snippet}"
    if start + max_length < len(body):
        snippet = f"{snippet}..."
    return snippet


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2]


def _normalize_text(text: str) -> str:
    return text.lower().replace("ё", "е")


def _parse_search_filters(query: str) -> tuple[str, dict[str, str]]:
    filters: dict[str, str] = {}
    terms = []
    for part in query.split():
        key, separator, value = part.partition(":")
        if separator and key in {"type", "tag", "space", "after"} and value:
            filters[key] = value.strip()
            continue
        terms.append(part)
    return " ".join(terms).strip(), filters


def _decision_note_body(prompt: str, related: list[MemorySearchResult]) -> str:
    parts = [part.strip() for part in re.split(r"[;\n]+", prompt) if part.strip()]
    options = parts[1:] if len(parts) > 1 else []
    lines = [
        "# Решение",
        "",
        "## Вопрос",
        prompt,
        "",
        "## Варианты",
    ]
    if options:
        lines.extend(f"- {option}" for option in options)
    else:
        lines.append("- ")
    lines.extend(
        [
            "",
            "## За",
            "- ",
            "",
            "## Против",
            "- ",
            "",
            "## Риски",
            "- ",
            "",
            "## Следующий шаг",
            "- ",
        ]
    )
    if related:
        lines.extend(["", "## Связанный контекст"])
        lines.extend(f"- {result.snippet} ({result.citation})" for result in related)
    return "\n".join(lines)


def _format_counter(counter: Counter[str], *, limit: int = 6) -> str:
    items = counter.most_common(limit)
    if not items:
        return "нет"
    return ", ".join(f"{name}: {count}" for name, count in items)


def parse_reminder_request(
    text: str,
    *,
    now: datetime | None = None,
    timezone_name: str = "Europe/Moscow",
) -> tuple[datetime, str]:
    clean = text.strip()
    if not clean:
        raise ValueError("Укажи время и текст напоминания.")

    timezone = ZoneInfo(timezone_name)
    current = now or datetime.now(timezone)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone)
    current = current.astimezone(timezone)

    relative = re.match(
        r"^(?:через\s+)?(?P<count>\d+)\s*"
        r"(?P<unit>минут[уы]?|мин|час(?:а|ов)?|д(?:ень|ня|ней)?)\s+"
        r"(?P<body>.+)$",
        clean,
        flags=re.IGNORECASE,
    )
    if relative:
        count = int(relative.group("count"))
        unit = relative.group("unit").lower()
        if unit.startswith("мин"):
            due_at = current + timedelta(minutes=count)
        elif unit.startswith("час"):
            due_at = current + timedelta(hours=count)
        else:
            due_at = current + timedelta(days=count)
        return due_at.astimezone(UTC), relative.group("body").strip()

    tomorrow = re.match(
        r"^завтра(?:\s+(?P<time>\d{1,2}:\d{2}))?\s+(?P<body>.+)$",
        clean,
        flags=re.IGNORECASE,
    )
    if tomorrow:
        due_at = _local_due_datetime(
            current=current,
            date_text=None,
            clock_text=tomorrow.group("time"),
            day_offset=1,
            timezone=timezone,
        )
        return due_at.astimezone(UTC), tomorrow.group("body").strip()

    today = re.match(
        r"^сегодня\s+(?P<time>\d{1,2}:\d{2})\s+(?P<body>.+)$",
        clean,
        flags=re.IGNORECASE,
    )
    if today:
        due_at = _local_due_datetime(
            current=current,
            date_text=None,
            clock_text=today.group("time"),
            day_offset=0,
            timezone=timezone,
        )
        if due_at <= current:
            raise ValueError("Время сегодня уже прошло.")
        return due_at.astimezone(UTC), today.group("body").strip()

    absolute = re.match(
        r"^(?P<date>\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})"
        r"(?:\s+(?P<time>\d{1,2}:\d{2}))?\s+"
        r"(?P<body>.+)$",
        clean,
    )
    if absolute:
        due_at = _local_due_datetime(
            current=current,
            date_text=absolute.group("date"),
            clock_text=absolute.group("time"),
            day_offset=0,
            timezone=timezone,
        )
        if due_at <= current:
            raise ValueError("Дата напоминания уже прошла.")
        return due_at.astimezone(UTC), absolute.group("body").strip()

    raise ValueError(
        "Не понял время. Примеры: /remind через 10 минут проверить духовку, "
        "/remind завтра 09:00 купить молоко."
    )


def _local_due_datetime(
    *,
    current: datetime,
    date_text: str | None,
    clock_text: str | None,
    day_offset: int,
    timezone: ZoneInfo,
) -> datetime:
    hour, minute = _parse_clock(clock_text)
    if date_text is None:
        due_date = (current + timedelta(days=day_offset)).date()
    elif "." in date_text:
        due_date = datetime.strptime(date_text, "%d.%m.%Y").date()
    else:
        due_date = datetime.fromisoformat(date_text).date()
    return datetime(
        due_date.year,
        due_date.month,
        due_date.day,
        hour,
        minute,
        tzinfo=timezone,
    )


def _parse_clock(clock_text: str | None) -> tuple[int, int]:
    if clock_text is None:
        return 9, 0
    hour_text, _, minute_text = clock_text.partition(":")
    hour = int(hour_text)
    minute = int(minute_text)
    if hour > 23 or minute > 59:
        raise ValueError("Некорректное время напоминания.")
    return hour, minute


def _normalize_space(space: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", space.strip().lower()).strip("-")
    return normalized or DEFAULT_SPACE


def parse_space_prefix(text: str, *, default_space: str = DEFAULT_SPACE) -> tuple[str, str]:
    clean = text.strip()
    match = re.match(r"^@(?P<space>[a-zA-Z0-9_-]+)\s+(?P<body>.+)$", clean, flags=re.DOTALL)
    if match is None:
        return _normalize_space(default_space), clean
    return _normalize_space(match.group("space")), match.group("body").strip()


def _unique_markdown_path(directory: Path, stem: str) -> Path:
    path = directory / f"{stem}.md"
    if not path.exists():
        return path
    suffix = 2
    while True:
        candidate = directory / f"{stem}-{suffix}.md"
        if not candidate.exists():
            return candidate
        suffix += 1


def _checksum(text: str, *, source_url: str | None = None) -> str:
    normalized = " ".join(text.strip().split()).lower()
    seed = f"{source_url or ''}\n{normalized}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _chunks(text: str, *, max_length: int = MAX_CHUNK_LENGTH) -> list[str]:
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs or [text.strip()]:
        if len(current) + len(paragraph) + 2 <= max_length:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= max_length:
            current = paragraph
        else:
            chunks.extend(
                paragraph[index : index + max_length]
                for index in range(0, len(paragraph), max_length)
            )
            current = ""
    if current:
        chunks.append(current)
    return chunks or [text[:max_length]]


def _fts_query(query: str) -> str:
    terms = [_soft_stem(token) or token for token in _tokens(query)]
    safe_terms = [term.replace('"', "") for term in terms if term.replace('"', "")]
    return " OR ".join(f'"{term}"' for term in dict.fromkeys(safe_terms))


def _frontmatter_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _unquote_frontmatter_value(value: str) -> str:
    clean = value.strip()
    if len(clean) >= 2 and clean.startswith('"') and clean.endswith('"'):
        return clean[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return clean


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


def _user_id_from_path(path: Path) -> int | None:
    parts = path.parts
    if "users" not in parts:
        return None
    index = parts.index("users")
    if index + 1 >= len(parts):
        return None
    try:
        return int(parts[index + 1])
    except ValueError:
        return None


def _soft_stem(token: str) -> str | None:
    if len(token) < 5:
        return None
    for suffix in (
        "ами",
        "ями",
        "ого",
        "ему",
        "ыми",
        "ими",
        "ов",
        "ев",
        "ей",
        "ам",
        "ям",
        "ах",
        "ях",
        "ые",
        "ие",
        "ый",
        "ий",
        "ая",
        "яя",
        "ой",
        "ей",
        "а",
        "я",
        "ы",
        "и",
        "е",
        "у",
        "ю",
    ):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return None


def _looks_completed(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(marker in normalized for marker in ("сделано", "готово", "выполнено", "done"))
