from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class PantryItem:
    id: str
    name: str
    quantity: Decimal
    unit: str
    expires_at: date | None = None
    created_at: datetime | None = None


class PantryStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def add_item(
        self,
        *,
        user_id: int,
        name: str,
        quantity: Decimal = Decimal("1"),
        unit: str = "шт",
        expires_at: date | None = None,
        now: datetime | None = None,
    ) -> PantryItem:
        clean_name = name.strip().lower()
        if not clean_name:
            raise ValueError("pantry item name is empty")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        items = self.list_items(user_id=user_id)
        existing_index = next(
            (
                index
                for index, item in enumerate(items)
                if item.name == clean_name and item.unit == unit and item.expires_at == expires_at
            ),
            None,
        )
        if existing_index is not None:
            existing = items[existing_index]
            item = PantryItem(
                id=existing.id,
                name=existing.name,
                quantity=existing.quantity + quantity,
                unit=existing.unit,
                expires_at=existing.expires_at,
                created_at=existing.created_at,
            )
            items[existing_index] = item
        else:
            item = PantryItem(
                id=secrets.token_hex(3),
                name=clean_name,
                quantity=quantity,
                unit=unit.strip() or "шт",
                expires_at=expires_at,
                created_at=(now or datetime.now(UTC)).astimezone(UTC),
            )
            items.append(item)
        self._write_items(user_id=user_id, items=items)
        return item

    def list_items(self, *, user_id: int) -> list[PantryItem]:
        path = self._path(user_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = [_item_from_dict(item) for item in raw]
        items.sort(key=lambda item: (item.expires_at or date.max, item.name))
        return items

    def consume(self, *, user_id: int, item_ref: str, quantity: Decimal) -> bool:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        normalized = item_ref.strip().lower()
        items = self.list_items(user_id=user_id)
        changed = False
        remaining: list[PantryItem] = []
        for item in items:
            matches = item.id == normalized or item.name == normalized
            if matches and not changed:
                new_quantity = item.quantity - quantity
                changed = True
                if new_quantity > 0:
                    remaining.append(
                        PantryItem(
                            id=item.id,
                            name=item.name,
                            quantity=new_quantity,
                            unit=item.unit,
                            expires_at=item.expires_at,
                            created_at=item.created_at,
                        )
                    )
                continue
            remaining.append(item)
        if changed:
            self._write_items(user_id=user_id, items=remaining)
        return changed

    def expiring_items(
        self,
        *,
        user_id: int,
        within_days: int = 3,
        today: date | None = None,
    ) -> list[PantryItem]:
        current = today or datetime.now(UTC).date()
        cutoff = current + timedelta(days=within_days)
        return [
            item
            for item in self.list_items(user_id=user_id)
            if item.expires_at is not None and item.expires_at <= cutoff
        ]

    def shopping_suggestions(self, *, user_id: int) -> list[str]:
        items = self.list_items(user_id=user_id)
        names = {item.name for item in items if item.quantity > 0}
        staples = ["молоко", "яйца", "хлеб", "кофе", "сахар"]
        return [name for name in staples if name not in names]

    def _write_items(self, *, user_id: int, items: list[PantryItem]) -> None:
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([_item_to_dict(item) for item in items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "pantry.json"


def parse_pantry_item(text: str) -> tuple[str, Decimal, str, date | None]:
    clean = text.strip()
    if not clean:
        raise ValueError("Использование: /pantry_add <товар> [кол-во] [ед] [YYYY-MM-DD]")
    expires_at = None
    date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})$", clean)
    if date_match:
        expires_at = date.fromisoformat(date_match.group(1))
        clean = clean[: date_match.start()].strip()
    parts = clean.split()
    if len(parts) >= 2:
        quantity = _decimal_or_none(parts[-2])
        if quantity is not None:
            return " ".join(parts[:-2]), quantity, parts[-1], expires_at
        quantity = _decimal_or_none(parts[-1])
        if quantity is not None:
            return " ".join(parts[:-1]), quantity, "шт", expires_at
    return clean, Decimal("1"), "шт", expires_at


def format_pantry(items: list[PantryItem]) -> str:
    if not items:
        return "Домашний склад пуст."
    lines = ["Домашний склад:"]
    for item in items:
        expiry = f", до {item.expires_at.isoformat()}" if item.expires_at else ""
        lines.append(
            f"- {item.id}: {item.name} — "
            f"{_format_decimal(item.quantity)} {item.unit}{expiry}"
        )
    return "\n".join(lines)


def format_pantry_suggestions(suggestions: list[str]) -> str:
    if not suggestions:
        return "Базовые продукты на складе есть."
    return "Можно докупить:\n" + "\n".join(f"- {item}" for item in suggestions)


def _decimal_or_none(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _item_to_dict(item: PantryItem) -> dict[str, object]:
    return {
        "id": item.id,
        "name": item.name,
        "quantity": str(item.quantity),
        "unit": item.unit,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "created_at": (item.created_at or datetime.now(UTC)).isoformat(),
    }


def _item_from_dict(raw: dict[str, object]) -> PantryItem:
    expires_at = raw.get("expires_at")
    created_at = raw.get("created_at")
    return PantryItem(
        id=str(raw["id"]),
        name=str(raw["name"]),
        quantity=Decimal(str(raw["quantity"])),
        unit=str(raw["unit"]),
        expires_at=date.fromisoformat(str(expires_at)) if expires_at else None,
        created_at=datetime.fromisoformat(str(created_at)).astimezone(UTC)
        if created_at
        else None,
    )
