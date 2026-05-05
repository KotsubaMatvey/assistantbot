from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

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
URL_RE = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class MemoryNoteMetadata:
    note_type: str
    tags: list[str]


@dataclass(frozen=True)
class MemorySearchResult:
    path: Path
    score: int
    snippet: str
    note_type: str = "note"
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PriceMemoryContext:
    remembered_cards: list[str] = field(default_factory=list)
    disliked_stores: list[str] = field(default_factory=list)
    excluded_stores: list[str] = field(default_factory=list)
    frequent_items: list[str] = field(default_factory=list)
    related_notes: list[MemorySearchResult] = field(default_factory=list)


class ObsidianMemory:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def remember_user_note(
        self,
        *,
        user_id: int,
        text: str,
        created_at: datetime | None = None,
    ) -> Path:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("memory text is empty")

        created = created_at or datetime.now(UTC)
        metadata = classify_note(clean_text)
        directory = self._user_notes_dir(user_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{created.strftime('%Y%m%d-%H%M%S-%f')}.md"
        path.write_text(
            _markdown_note(
                note_type=metadata.note_type,
                user_id=user_id,
                created_at=created,
                tags=metadata.tags,
                body=clean_text,
            ),
            encoding="utf-8",
        )
        self._append_daily_entry(user_id, created, "Память", clean_text)
        self._append_inbox_entry(user_id, created, clean_text, path)
        if metadata.note_type in {"fact", "preference", "task", "link"}:
            self._append_profile_fact(user_id, clean_text)
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
        path = directory / f"{created.strftime('%Y%m%d-%H%M%S-%f')}.md"
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
    ) -> list[MemorySearchResult]:
        tokens = _tokens(query)
        expanded = _expand_terms(tokens)
        if not expanded:
            return []

        results: list[MemorySearchResult] = []
        for path, text in self._iter_user_markdown(user_id):
            metadata = _parse_frontmatter(text)
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

    def settings_with_memory(self, settings: Any, context: PriceMemoryContext) -> object:
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
        counts: Counter[str] = Counter()
        for path in self._user_baskets_dir(user_id).glob("*.md"):
            body = _strip_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
            for line in body.splitlines():
                if line.startswith("- "):
                    counts[line[2:].strip().lower()] += 1
        frequent: list[str] = []
        for item_name in item_names:
            for saved, count in counts.items():
                if count >= min_count and item_name and item_name in saved:
                    frequent.append(item_name)
                    break
        return list(dict.fromkeys(frequent))[:5]

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


def classify_note(text: str) -> MemoryNoteMetadata:
    lowered = _normalize_text(text)
    tags = ["pricebot", "memory"]
    note_type = "fact"
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
) -> str:
    tags_text = ", ".join(tags)
    return "\n".join(
        [
            "---",
            f"type: {note_type}",
            f"user_id: {user_id}",
            f"created_at: {created_at.isoformat()}",
            f"tags: [{tags_text}]",
            "---",
            "",
            body.strip(),
            "",
        ]
    )


def _parse_frontmatter(text: str) -> MemoryNoteMetadata:
    if not text.startswith("---"):
        return MemoryNoteMetadata(note_type="note", tags=[])
    parts = text.split("---", 2)
    if len(parts) < 3:
        return MemoryNoteMetadata(note_type="note", tags=[])
    note_type = "note"
    tags: list[str] = []
    for line in parts[1].splitlines():
        if line.startswith("type:"):
            note_type = line.partition(":")[2].strip() or "note"
        if line.startswith("tags:"):
            raw = line.partition(":")[2].strip().strip("[]")
            tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
    return MemoryNoteMetadata(note_type=note_type, tags=tags)


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[\wа-яА-ЯёЁ]+", _normalize_text(text))
        if len(token) > 1
    ]


def _expand_terms(tokens: list[str]) -> list[str]:
    expanded = set(tokens)
    for token in tokens:
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
