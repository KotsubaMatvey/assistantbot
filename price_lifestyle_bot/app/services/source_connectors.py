from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.services.file_io import atomic_write_text
from app.services.knowledge_ingestion import (
    fetch_feed_digests,
    fetch_page_summary,
    format_digest_memory_note,
    format_feed_digests,
    format_learned_page_note,
    validate_public_url,
)
from app.services.obsidian_memory import ObsidianMemory


@dataclass(frozen=True)
class SourceRecord:
    id: str
    type: str
    url: str
    sync_interval_minutes: int = 60
    trust_level: str = "normal"
    enabled: bool = True
    last_sync_at: datetime | None = None
    last_error: str = ""
    cursor: str = ""
    items_seen: list[str] | None = None


@dataclass(frozen=True)
class SourceSyncResult:
    source_id: str
    ok: bool
    message: str
    stored: bool = False


class SourceStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def add_source(
        self,
        *,
        user_id: int,
        source_type: str,
        target: str,
        sync_interval_minutes: int = 60,
        trust_level: str = "normal",
    ) -> SourceRecord:
        normalized_type = _normalize_source_type(source_type)
        clean_url = _normalize_source_url(normalized_type, target)
        interval = max(5, sync_interval_minutes)
        sources = self.list_sources(user_id=user_id)
        existing = next(
            (
                source
                for source in sources
                if source.type == normalized_type and source.url == clean_url
            ),
            None,
        )
        if existing is not None:
            return existing
        source = SourceRecord(
            id=f"src_{secrets.token_hex(4)}",
            type=normalized_type,
            url=clean_url,
            sync_interval_minutes=interval,
            trust_level=trust_level or "normal",
        )
        self._write_sources(user_id, [*sources, source])
        return source

    def list_sources(self, *, user_id: int) -> list[SourceRecord]:
        path = self._sources_path(user_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [_source_from_dict(item) for item in raw]

    def delete_source(self, *, user_id: int, source_id: str) -> bool:
        sources = self.list_sources(user_id=user_id)
        remaining = [source for source in sources if source.id != source_id]
        if len(remaining) == len(sources):
            return False
        self._write_sources(user_id, remaining)
        return True

    async def sync_sources(
        self,
        *,
        user_id: int,
        memory: ObsidianMemory,
        source_id: str | None = None,
    ) -> list[SourceSyncResult]:
        sources = [
            source
            for source in self.list_sources(user_id=user_id)
            if source.enabled and (source_id is None or source.id == source_id)
        ]
        results = []
        for source in sources:
            result, updated = await self._sync_one(user_id=user_id, memory=memory, source=source)
            self._replace_source(user_id=user_id, source=updated)
            results.append(result)
        return results

    async def _sync_one(
        self,
        *,
        user_id: int,
        memory: ObsidianMemory,
        source: SourceRecord,
    ) -> tuple[SourceSyncResult, SourceRecord]:
        try:
            if source.type == "rss":
                digests = await fetch_feed_digests([source.url], limit_per_feed=5)
                text = format_digest_memory_note(digests)
                memory.remember_user_note(
                    user_id=user_id,
                    text=text,
                    note_type="source",
                    extra_tags=["source", "rss"],
                    source_type="rss",
                    source_url=source.url,
                    title=f"RSS source: {source.url}",
                )
                message = format_feed_digests(digests)[:500]
            elif source.type == "url":
                page = await fetch_page_summary(source.url)
                memory.remember_user_note(
                    user_id=user_id,
                    text=format_learned_page_note(page),
                    note_type="source",
                    extra_tags=["source", "web"],
                    source_type="web",
                    source_url=source.url,
                    title=page.title,
                )
                message = f"URL synced: {page.title}"
            elif source.type == "github":
                summary = await fetch_github_repo_summary(source.url)
                memory.remember_user_note(
                    user_id=user_id,
                    text=summary,
                    note_type="source",
                    extra_tags=["source", "github"],
                    source_type="github",
                    source_url=source.url,
                    title=f"GitHub source: {source.url}",
                )
                message = f"GitHub synced: {source.url}"
            else:
                raise ValueError("unsupported source type")
        except Exception as exc:
            error = str(exc)[:300]
            return (
                SourceSyncResult(source_id=source.id, ok=False, message=error),
                replace(source, last_error=error),
            )

        return (
            SourceSyncResult(source_id=source.id, ok=True, message=message, stored=True),
            replace(source, last_sync_at=datetime.now(UTC), last_error=""),
        )

    def _replace_source(self, *, user_id: int, source: SourceRecord) -> None:
        sources = self.list_sources(user_id=user_id)
        self._write_sources(
            user_id,
            [source if existing.id == source.id else existing for existing in sources],
        )

    def _write_sources(self, user_id: int, sources: list[SourceRecord]) -> None:
        path = self._sources_path(user_id)
        atomic_write_text(
            path,
            json.dumps(
                [_source_to_dict(source) for source in sources],
                ensure_ascii=False,
                indent=2,
            ),
        )

    def _sources_path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "sources" / "sources.json"


async def fetch_github_repo_summary(repo_url: str) -> str:
    repo = _github_repo_from_url(repo_url)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"https://api.github.com/repos/{repo}",
            headers={"User-Agent": "assistantbot/0.1"},
        )
        response.raise_for_status()
        data = response.json()
    description = data.get("description") or ""
    return "\n".join(
        [
            f"GitHub repository: {repo}",
            f"URL: {repo_url}",
            f"Description: {description}",
            f"Stars: {data.get('stargazers_count', 0)}",
            f"Forks: {data.get('forks_count', 0)}",
            f"Open issues: {data.get('open_issues_count', 0)}",
            f"Default branch: {data.get('default_branch', '')}",
        ]
    )


def format_sources(sources: list[SourceRecord]) -> str:
    if not sources:
        return "Unified sources пока не добавлены."
    lines = ["Unified sources:"]
    for source in sources:
        status = "enabled" if source.enabled else "disabled"
        synced = source.last_sync_at.isoformat() if source.last_sync_at else "never"
        error = f"\n  last_error: {source.last_error}" if source.last_error else ""
        lines.append(
            f"- {source.id}: {source.type} {source.url}\n"
            f"  interval: {source.sync_interval_minutes}m; trust: {source.trust_level}; "
            f"{status}; last_sync: {synced}{error}"
        )
    return "\n".join(lines)


def format_source_sync_results(results: list[SourceSyncResult]) -> str:
    if not results:
        return "Нет enabled sources для sync."
    lines = ["Source sync:"]
    for result in results:
        mark = "OK" if result.ok else "FAIL"
        lines.append(f"- {mark} {result.source_id}: {result.message}")
    return "\n".join(lines)


def _normalize_source_type(source_type: str) -> str:
    normalized = source_type.strip().lower()
    if normalized not in {"rss", "url", "github"}:
        raise ValueError("source type must be rss, url, or github")
    return normalized


def _normalize_source_url(source_type: str, target: str) -> str:
    clean = target.strip()
    if source_type in {"rss", "url"}:
        return validate_public_url(clean)
    return f"https://github.com/{_github_repo_from_url(clean)}"


def _github_repo_from_url(value: str) -> str:
    clean = value.strip()
    if not clean:
        raise ValueError("github repo is empty")
    if "://" not in clean and re.fullmatch(r"[\w.-]+/[\w.-]+", clean):
        return clean
    parsed = urlparse(clean)
    if parsed.netloc.lower() != "github.com":
        raise ValueError("github source must be owner/repo or https://github.com/owner/repo")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise ValueError("github source must include owner and repo")
    return f"{parts[0]}/{parts[1]}"


def _source_to_dict(source: SourceRecord) -> dict[str, object]:
    return {
        "id": source.id,
        "type": source.type,
        "url": source.url,
        "sync_interval_minutes": source.sync_interval_minutes,
        "trust_level": source.trust_level,
        "enabled": source.enabled,
        "last_sync_at": source.last_sync_at.isoformat() if source.last_sync_at else "",
        "last_error": source.last_error,
        "cursor": source.cursor,
        "items_seen": source.items_seen or [],
    }


def _source_from_dict(raw: dict[str, object]) -> SourceRecord:
    return SourceRecord(
        id=str(raw.get("id", "")),
        type=str(raw.get("type", "")),
        url=str(raw.get("url", "")),
        sync_interval_minutes=int(raw.get("sync_interval_minutes", 60)),
        trust_level=str(raw.get("trust_level", "normal")),
        enabled=bool(raw.get("enabled", True)),
        last_sync_at=_parse_datetime(str(raw.get("last_sync_at", ""))),
        last_error=str(raw.get("last_error", "")),
        cursor=str(raw.get("cursor", "")),
        items_seen=[str(item) for item in raw.get("items_seen", []) or []],
    )


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
