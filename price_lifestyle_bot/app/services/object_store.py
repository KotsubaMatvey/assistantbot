from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.file_io import atomic_write_text

OBJECT_TYPES = {
    "note",
    "task",
    "person",
    "project",
    "source",
    "receipt",
    "product",
    "decision",
}


@dataclass(frozen=True)
class AssistantObject:
    id: str
    type: str
    title: str
    body: str = ""
    tags: list[str] = field(default_factory=list)
    relations: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = "manual"


@dataclass(frozen=True)
class ObjectStats:
    total: int
    by_type: list[tuple[str, int]]


class ObjectStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def upsert_object(
        self,
        *,
        user_id: int,
        object_type: str,
        title: str,
        body: str = "",
        tags: list[str] | None = None,
        relations: dict[str, str] | None = None,
        source: str = "manual",
        created_at: datetime | None = None,
        object_id: str | None = None,
    ) -> AssistantObject:
        clean_type = object_type.strip().lower()
        if clean_type not in OBJECT_TYPES:
            raise ValueError("unsupported object type")
        clean_title = " ".join(title.strip().split())
        if not clean_title:
            raise ValueError("object title is empty")
        clean_relations = {
            str(key): str(value)
            for key, value in (relations or {}).items()
            if str(key).strip() and str(value).strip()
        }
        clean_source = source.strip() or "manual"
        obj = AssistantObject(
            id=object_id
            or _object_id(clean_type, clean_title, clean_source, clean_relations),
            type=clean_type,
            title=clean_title,
            body=body.strip(),
            tags=list(dict.fromkeys(normalize_tag(tag) for tag in tags or [] if tag.strip())),
            relations=clean_relations,
            created_at=(created_at or datetime.now(UTC)).astimezone(UTC),
            source=clean_source,
        )
        objects = self.list_objects(user_id=user_id, limit=10_000)
        replaced = False
        updated: list[AssistantObject] = []
        for existing in objects:
            if existing.id == obj.id:
                updated.append(obj)
                replaced = True
            else:
                updated.append(existing)
        if not replaced:
            updated.append(obj)
        self._write_objects(user_id=user_id, objects=updated)
        return obj

    def list_objects(
        self,
        *,
        user_id: int,
        object_type: str | None = None,
        limit: int = 50,
    ) -> list[AssistantObject]:
        path = self._objects_path(user_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        objects = [_object_from_dict(item) for item in raw if isinstance(item, dict)]
        if object_type is not None:
            clean_type = object_type.strip().lower()
            objects = [obj for obj in objects if obj.type == clean_type]
        objects.sort(key=lambda obj: obj.created_at, reverse=True)
        return objects[:limit]

    def stats(self, *, user_id: int) -> ObjectStats:
        objects = self.list_objects(user_id=user_id, limit=10_000)
        counter = Counter(obj.type for obj in objects)
        return ObjectStats(
            total=len(objects),
            by_type=sorted(counter.items(), key=lambda item: (-item[1], item[0])),
        )

    def index_markdown_note(self, *, user_id: int, path: Path) -> AssistantObject | None:
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8", errors="ignore")
        metadata = _frontmatter(text)
        body = _strip_frontmatter(text).strip()
        if not body:
            return None
        note_type = metadata.get("type", "note") or "note"
        source_type = metadata.get("source_type", "manual") or "manual"
        source_url = _unquote(metadata.get("source_url", ""))
        object_type = _object_type(
            note_type=note_type,
            source_type=source_type,
            source_url=source_url,
        )
        tags = _parse_tags(metadata.get("tags", ""))
        title = _object_title(
            object_type=object_type,
            metadata_title=_unquote(metadata.get("title", "")),
            body=body,
            path=path,
        )
        relations = {
            "note_path": str(path),
            "note_type": note_type,
            "space": metadata.get("space", "default") or "default",
            "source_type": source_type,
        }
        if source_url:
            relations["source_url"] = source_url
        return self.upsert_object(
            user_id=user_id,
            object_type=object_type,
            title=title,
            body=body[:1200],
            tags=tags,
            relations=relations,
            source=source_url or source_type,
            created_at=_parse_datetime(metadata.get("created_at", "")),
            object_id=_note_object_id(
                object_type=object_type,
                title=title,
                path=path,
                source=source_url,
            ),
        )

    def index_recent_notes(self, *, user_id: int, memory: Any, limit: int = 500) -> int:
        count = 0
        for note in memory.recent_notes(user_id=user_id, limit=limit):
            if self.index_markdown_note(user_id=user_id, path=note.path) is not None:
                count += 1
        return count

    def index_receipt(
        self,
        *,
        user_id: int,
        receipt_id: str,
        store: str,
        total: str,
        items: list[tuple[str, str, str]],
        purchased_at: datetime,
    ) -> None:
        body = "\n".join(f"- {name}: {price} ({category})" for name, price, category in items)
        self.upsert_object(
            user_id=user_id,
            object_type="receipt",
            title=f"Receipt: {store} {purchased_at.date().isoformat()}",
            body=f"Total: {total}\n{body}",
            tags=["receipt", normalize_tag(store)],
            relations={"receipt_id": receipt_id, "store": store},
            source="receipt",
            created_at=purchased_at,
            object_id=f"obj_receipt_{receipt_id}",
        )
        for name, price, category in items:
            self.upsert_object(
                user_id=user_id,
                object_type="product",
                title=name,
                body=f"Last receipt price: {price}",
                tags=["product", normalize_tag(category)],
                relations={"last_receipt_id": receipt_id, "category": category},
                source="receipt",
                created_at=purchased_at,
            )

    def _write_objects(self, *, user_id: int, objects: list[AssistantObject]) -> None:
        path = self._objects_path(user_id)
        atomic_write_text(
            path,
            json.dumps([_object_to_dict(obj) for obj in objects], ensure_ascii=False, indent=2),
        )

    def _objects_path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "objects" / "objects.json"


def format_objects(objects: list[AssistantObject]) -> str:
    if not objects:
        return "Objects are empty."
    lines = ["Objects:"]
    for obj in objects:
        tags = f" [{', '.join(obj.tags[:4])}]" if obj.tags else ""
        lines.append(f"- {obj.type}:{obj.title}{tags}\n  id: {obj.id}")
    return "\n".join(lines)


def format_object_stats(stats: ObjectStats) -> str:
    lines = ["Object system", f"Total: {stats.total}"]
    if stats.by_type:
        lines.append("Types:")
        lines.extend(f"- {object_type}: {count}" for object_type, count in stats.by_type)
    return "\n".join(lines)


def normalize_tag(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ_-]+", "-", value.strip().lower())
    return normalized.strip("-") or "untagged"


def _object_id(
    object_type: str,
    title: str,
    source: str,
    relations: dict[str, str],
) -> str:
    seed = f"{object_type}\n{title}\n{source}\n{json.dumps(relations, sort_keys=True)}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"obj_{digest}"


def _note_object_id(*, object_type: str, title: str, path: Path, source: str) -> str:
    if object_type in {"person", "project", "source", "product"}:
        return _object_id(object_type, title, source or "manual", {})
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]
    return f"obj_{digest}"


def _object_type(*, note_type: str, source_type: str, source_url: str) -> str:
    if source_url or source_type not in {"", "manual", "reminder"} or note_type == "link":
        return "source"
    if note_type in {"task", "reminder"}:
        return "task"
    if note_type in {"person", "decision"}:
        return note_type
    return "note"


def _object_title(*, object_type: str, metadata_title: str, body: str, path: Path) -> str:
    if metadata_title:
        return metadata_title[:120]
    if object_type == "person":
        for line in body.splitlines():
            if line.lower().startswith("person:"):
                return line.partition(":")[2].strip()[:120] or path.stem
    for line in body.splitlines():
        clean = line.strip("#- ")
        if clean:
            return clean[:120]
    return path.stem


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
            fields[key.strip()] = value.strip()
    return fields


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    return parts[2] if len(parts) >= 3 else text


def _parse_tags(value: str) -> list[str]:
    return [normalize_tag(tag) for tag in value.strip("[]").split(",") if tag.strip()]


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _unquote(value: str) -> str:
    clean = value.strip()
    if len(clean) >= 2 and clean.startswith('"') and clean.endswith('"'):
        return clean[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return clean


def _object_to_dict(obj: AssistantObject) -> dict[str, object]:
    return {
        "id": obj.id,
        "type": obj.type,
        "title": obj.title,
        "body": obj.body,
        "tags": obj.tags,
        "relations": obj.relations,
        "created_at": obj.created_at.isoformat(),
        "source": obj.source,
    }


def _object_from_dict(raw: dict[str, object]) -> AssistantObject:
    raw_tags = raw.get("tags", [])
    raw_relations = raw.get("relations", {})
    return AssistantObject(
        id=str(raw["id"]),
        type=str(raw["type"]),
        title=str(raw["title"]),
        body=str(raw.get("body", "")),
        tags=[str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else [],
        relations=(
            {str(key): str(value) for key, value in raw_relations.items()}
            if isinstance(raw_relations, dict)
            else {}
        ),
        created_at=_parse_datetime(str(raw.get("created_at", ""))),
        source=str(raw.get("source", "manual")),
    )
