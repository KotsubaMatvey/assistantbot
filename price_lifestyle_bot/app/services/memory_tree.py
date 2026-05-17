from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.services.obsidian_memory import MemorySearchResult, ObsidianMemory


@dataclass(frozen=True)
class MemoryTreeBuildResult:
    raw_captures: int
    daily_summaries: int
    project_summaries: int
    profile_path: Path
    weekly_path: Path


@dataclass(frozen=True)
class MemoryHealth:
    raw_captures: int
    daily_summaries: int
    project_summaries: int
    profile_exists: bool
    weekly_exists: bool
    latest_raw: str = ""
    latest_summary: str = ""


@dataclass(frozen=True)
class NoteSnapshot:
    path: Path
    created_at: datetime
    note_type: str
    tags: list[str]
    body: str
    title: str = ""


@dataclass(frozen=True)
class SummarySection:
    title: str
    items: list[str] = field(default_factory=list)


class MemoryTreeStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def rebuild_tree(
        self,
        *,
        memory: ObsidianMemory,
        user_id: int,
        now: datetime | None = None,
    ) -> MemoryTreeBuildResult:
        notes = _load_notes(memory, user_id=user_id)
        daily_count = self._write_daily_summaries(user_id=user_id, notes=notes)
        weekly_path = self.write_weekly_summary(user_id=user_id, notes=notes, now=now)
        project_count = self._write_project_summaries(user_id=user_id, notes=notes)
        profile_path = self.write_profile(user_id=user_id, notes=notes)
        return MemoryTreeBuildResult(
            raw_captures=len(notes),
            daily_summaries=daily_count,
            project_summaries=project_count,
            profile_path=profile_path,
            weekly_path=weekly_path,
        )

    def health(self, *, memory: ObsidianMemory, user_id: int) -> MemoryHealth:
        notes = _load_notes(memory, user_id=user_id)
        latest_raw = max((note.created_at for note in notes), default=None)
        latest_summary = max(
            (path.stat().st_mtime for path in self._tree_dir(user_id).rglob("*.md")),
            default=None,
        )
        return MemoryHealth(
            raw_captures=len(notes),
            daily_summaries=len(list(self._daily_dir(user_id).glob("*.md"))),
            project_summaries=len(list(self._projects_dir(user_id).glob("*.md"))),
            profile_exists=self._profile_path(user_id).exists(),
            weekly_exists=any(self._weekly_dir(user_id).glob("*.md")),
            latest_raw=latest_raw.date().isoformat() if latest_raw else "",
            latest_summary=(
                datetime.fromtimestamp(latest_summary, tz=UTC).date().isoformat()
                if latest_summary
                else ""
            ),
        )

    def format_tree(self, *, memory: ObsidianMemory, user_id: int) -> str:
        health = self.health(memory=memory, user_id=user_id)
        return "\n".join(
            [
                "Memory Tree",
                f"Raw captures: {health.raw_captures}",
                f"Daily summaries: {health.daily_summaries}",
                f"Project summaries: {health.project_summaries}",
                f"Profile: {'ready' if health.profile_exists else 'missing'}",
                f"Weekly: {'ready' if health.weekly_exists else 'missing'}",
                f"Latest raw: {health.latest_raw or 'n/a'}",
                f"Latest summary: {health.latest_summary or 'n/a'}",
                "",
                "Structure:",
                "Raw captures -> daily summaries -> project summaries -> long-term profile",
            ]
        )

    def write_weekly_summary(
        self,
        *,
        user_id: int,
        notes: list[NoteSnapshot] | None = None,
        memory: ObsidianMemory | None = None,
        now: datetime | None = None,
    ) -> Path:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        if notes is None:
            if memory is None:
                raise ValueError("memory is required when notes are not provided")
            notes = _load_notes(memory, user_id=user_id)
        start = current - timedelta(days=7)
        recent = [note for note in notes if start <= note.created_at <= current]
        path = self._weekly_dir(user_id) / f"{current.date().isoformat()}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _summary_markdown(
                title=f"Weekly summary {current.date().isoformat()}",
                sections=_summary_sections(recent),
                sources=recent,
            ),
            encoding="utf-8",
        )
        return path

    def weekly_summary(
        self,
        *,
        user_id: int,
        memory: ObsidianMemory,
        now: datetime | None = None,
    ) -> str:
        notes = _load_notes(memory, user_id=user_id)
        path = self.write_weekly_summary(user_id=user_id, notes=notes, now=now)
        return path.read_text(encoding="utf-8", errors="ignore")[:3900]

    def write_project_summary(
        self,
        *,
        user_id: int,
        project: str,
        memory: ObsidianMemory,
    ) -> Path:
        clean_project = project.strip()
        if not clean_project:
            raise ValueError("project is empty")
        results = memory.filtered_search(user_id=user_id, query=clean_project, limit=30)
        notes = [_snapshot_from_result(result) for result in results]
        slug = _slug(clean_project)
        path = self._projects_dir(user_id) / f"{slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _summary_markdown(
                title=f"Project summary: {clean_project}",
                sections=_summary_sections(notes),
                sources=notes,
            ),
            encoding="utf-8",
        )
        return path

    def project_summary(
        self,
        *,
        user_id: int,
        project: str,
        memory: ObsidianMemory,
    ) -> str:
        path = self.write_project_summary(user_id=user_id, project=project, memory=memory)
        return path.read_text(encoding="utf-8", errors="ignore")[:3900]

    def write_profile(self, *, user_id: int, notes: list[NoteSnapshot]) -> Path:
        profile_notes = [
            note
            for note in notes
            if note.note_type in {"preference", "person", "decision", "important"}
            or {"preference", "person", "decision", "important"} & set(note.tags)
        ]
        path = self._profile_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _summary_markdown(
                title="Long-term memory profile",
                sections=_profile_sections(profile_notes),
                sources=profile_notes,
            ),
            encoding="utf-8",
        )
        return path

    def memory_profile(self, *, user_id: int, memory: ObsidianMemory) -> str:
        notes = _load_notes(memory, user_id=user_id)
        path = self.write_profile(user_id=user_id, notes=notes)
        return path.read_text(encoding="utf-8", errors="ignore")[:3900]

    def _write_daily_summaries(self, *, user_id: int, notes: list[NoteSnapshot]) -> int:
        grouped: dict[str, list[NoteSnapshot]] = defaultdict(list)
        for note in notes:
            grouped[note.created_at.date().isoformat()].append(note)
        for day, day_notes in grouped.items():
            path = self._daily_dir(user_id) / f"{day}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                _summary_markdown(
                    title=f"Daily summary {day}",
                    sections=_summary_sections(day_notes),
                    sources=day_notes,
                ),
                encoding="utf-8",
            )
        return len(grouped)

    def _write_project_summaries(self, *, user_id: int, notes: list[NoteSnapshot]) -> int:
        project_tags = _project_tags(notes)
        for tag in project_tags:
            project_notes = [note for note in notes if tag in note.tags]
            path = self._projects_dir(user_id) / f"{_slug(tag)}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                _summary_markdown(
                    title=f"Project summary: {tag}",
                    sections=_summary_sections(project_notes),
                    sources=project_notes,
                ),
                encoding="utf-8",
            )
        return len(project_tags)

    def _tree_dir(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "memory_tree"

    def _daily_dir(self, user_id: int) -> Path:
        return self._tree_dir(user_id) / "daily"

    def _weekly_dir(self, user_id: int) -> Path:
        return self._tree_dir(user_id) / "weekly"

    def _projects_dir(self, user_id: int) -> Path:
        return self._tree_dir(user_id) / "projects"

    def _profile_path(self, user_id: int) -> Path:
        return self._tree_dir(user_id) / "profile.md"


def format_build_result(result: MemoryTreeBuildResult) -> str:
    return "\n".join(
        [
            "Memory Tree rebuilt",
            f"Raw captures: {result.raw_captures}",
            f"Daily summaries: {result.daily_summaries}",
            f"Project summaries: {result.project_summaries}",
            f"Weekly: {result.weekly_path.name}",
            f"Profile: {result.profile_path.name}",
        ]
    )


def _load_notes(memory: ObsidianMemory, *, user_id: int) -> list[NoteSnapshot]:
    return [
        _snapshot_from_result(result)
        for result in memory.recent_notes(user_id=user_id, limit=5000)
    ]


def _snapshot_from_result(result: MemorySearchResult) -> NoteSnapshot:
    text = result.path.read_text(encoding="utf-8", errors="ignore")
    metadata = _frontmatter(text)
    return NoteSnapshot(
        path=result.path,
        created_at=_parse_datetime(metadata.get("created_at", "")),
        note_type=metadata.get("type", result.note_type),
        tags=_parse_tags(metadata.get("tags", "")) or result.tags,
        body=_strip_frontmatter(text).strip(),
        title=metadata.get("title", result.title or result.path.name),
    )


def _summary_sections(notes: list[NoteSnapshot]) -> list[SummarySection]:
    if not notes:
        return [SummarySection("No captures", ["No matching raw captures yet."])]
    sections = [
        SummarySection("Decisions", _items_for(notes, {"decision"})),
        SummarySection("Tasks", _items_for(notes, {"task", "reminder"})),
        SummarySection("Preferences", _items_for(notes, {"preference", "person"})),
        SummarySection("Facts", _items_for(notes, {"fact", "important", "journal", "link"})),
    ]
    return [section for section in sections if section.items]


def _profile_sections(notes: list[NoteSnapshot]) -> list[SummarySection]:
    if not notes:
        return [SummarySection("Profile", ["No stable profile notes yet."])]
    return [
        SummarySection("Stable preferences", _items_for(notes, {"preference"})),
        SummarySection("People", _items_for(notes, {"person"})),
        SummarySection("Decisions", _items_for(notes, {"decision"})),
        SummarySection("Important facts", _items_for(notes, {"important", "fact"})),
    ]


def _items_for(notes: list[NoteSnapshot], labels: set[str], limit: int = 8) -> list[str]:
    items = []
    for note in notes:
        if note.note_type not in labels and not labels & set(note.tags):
            continue
        items.append(f"{_first_sentence(note.body)} ({note.path.name})")
    return items[:limit]


def _summary_markdown(
    *,
    title: str,
    sections: list[SummarySection],
    sources: list[NoteSnapshot],
) -> str:
    lines = [f"# {title}", ""]
    for section in sections:
        if not section.items:
            continue
        lines.extend([f"## {section.title}"])
        lines.extend(f"- {item}" for item in section.items)
        lines.append("")
    lines.append("## Source notes")
    if sources:
        for note in sources[:20]:
            lines.append(f"- {note.path.name} | {note.created_at.date().isoformat()}")
    else:
        lines.append("- none")
    return "\n".join(lines).strip() + "\n"


def _project_tags(notes: list[NoteSnapshot]) -> list[str]:
    ignored = {
        "pricebot",
        "memory",
        "fact",
        "task",
        "preference",
        "person",
        "decision",
        "important",
        "journal",
        "link",
        "reminder",
        "shopping",
    }
    counts: Counter[str] = Counter()
    for note in notes:
        counts.update(tag for tag in note.tags if tag not in ignored)
    return [tag for tag, count in counts.most_common(10) if count >= 2]


def _first_sentence(text: str, max_length: int = 180) -> str:
    clean = " ".join(text.split())
    if not clean:
        return "empty note"
    sentence_end = clean.find(". ")
    if 0 < sentence_end < max_length:
        return clean[: sentence_end + 1]
    return clean[:max_length].rstrip() + ("..." if len(clean) > max_length else "")


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fields = {}
    for line in parts[1].splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip().strip('"')
    return fields


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    return parts[2] if len(parts) >= 3 else text


def _parse_tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.strip("[]").split(",") if tag.strip()]


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _slug(text: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ_-]+", "-", text.strip().lower())
    return raw.strip("-") or "project"
