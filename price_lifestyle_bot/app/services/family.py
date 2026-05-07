from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class FamilySpace:
    id: str
    name: str
    owner_id: int
    invite_code: str
    members: list[int] = field(default_factory=list)
    shared_items: list[str] = field(default_factory=list)
    created_at: datetime | None = None


class FamilyStore:
    def __init__(self, vault_path: str) -> None:
        self.path = Path(vault_path).expanduser() / "families" / "families.json"

    def create_family(self, *, owner_id: int, name: str) -> FamilySpace:
        clean_name = name.strip() or "Home"
        families = self.list_families()
        existing = next((family for family in families if owner_id in family.members), None)
        if existing is not None:
            return existing
        family = FamilySpace(
            id=secrets.token_hex(4),
            name=clean_name,
            owner_id=owner_id,
            invite_code=secrets.token_hex(3),
            members=[owner_id],
            created_at=datetime.now(UTC),
        )
        families.append(family)
        self._write(families)
        return family

    def join_family(self, *, user_id: int, invite_code: str) -> FamilySpace | None:
        families = self.list_families()
        updated: list[FamilySpace] = []
        joined: FamilySpace | None = None
        for family in families:
            if family.invite_code == invite_code.strip():
                members = list(dict.fromkeys([*family.members, user_id]))
                family = FamilySpace(
                    id=family.id,
                    name=family.name,
                    owner_id=family.owner_id,
                    invite_code=family.invite_code,
                    members=members,
                    shared_items=family.shared_items,
                    created_at=family.created_at,
                )
                joined = family
            updated.append(family)
        if joined is not None:
            self._write(updated)
        return joined

    def family_for_user(self, *, user_id: int) -> FamilySpace | None:
        return next((family for family in self.list_families() if user_id in family.members), None)

    def add_shared_item(self, *, user_id: int, text: str) -> FamilySpace | None:
        clean = text.strip()
        if not clean:
            raise ValueError("shared item is empty")
        families = self.list_families()
        updated: list[FamilySpace] = []
        changed: FamilySpace | None = None
        for family in families:
            if user_id in family.members:
                family = FamilySpace(
                    id=family.id,
                    name=family.name,
                    owner_id=family.owner_id,
                    invite_code=family.invite_code,
                    members=family.members,
                    shared_items=[*family.shared_items, clean],
                    created_at=family.created_at,
                )
                changed = family
            updated.append(family)
        if changed is not None:
            self._write(updated)
        return changed

    def list_families(self) -> list[FamilySpace]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [_family_from_dict(item) for item in raw]

    def _write(self, families: list[FamilySpace]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                [_family_to_dict(family) for family in families],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def format_family(family: FamilySpace | None) -> str:
    if family is None:
        return "Семейный режим не настроен. Используй /family_create <name>."
    lines = [
        f"Семья: {family.name}",
        f"Invite code: {family.invite_code}",
        f"Участников: {len(family.members)}",
    ]
    if family.shared_items:
        lines.append("Общий список:")
        lines.extend(f"- {item}" for item in family.shared_items[-20:])
    return "\n".join(lines)


def _family_to_dict(family: FamilySpace) -> dict[str, object]:
    return {
        "id": family.id,
        "name": family.name,
        "owner_id": family.owner_id,
        "invite_code": family.invite_code,
        "members": family.members,
        "shared_items": family.shared_items,
        "created_at": (family.created_at or datetime.now(UTC)).isoformat(),
    }


def _family_from_dict(raw: dict[str, object]) -> FamilySpace:
    raw_members = raw.get("members", [])
    raw_items = raw.get("shared_items", [])
    if not isinstance(raw_members, list):
        raw_members = []
    if not isinstance(raw_items, list):
        raw_items = []
    return FamilySpace(
        id=str(raw["id"]),
        name=str(raw["name"]),
        owner_id=int(str(raw["owner_id"])),
        invite_code=str(raw["invite_code"]),
        members=[int(item) for item in raw_members],
        shared_items=[str(item) for item in raw_items],
        created_at=datetime.fromisoformat(str(raw["created_at"])).astimezone(UTC),
    )
