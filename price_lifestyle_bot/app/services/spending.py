from __future__ import annotations

import json
import re
import secrets
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class ReceiptItem:
    name: str
    price: Decimal


@dataclass(frozen=True)
class Receipt:
    id: str
    user_id: int
    store: str
    items: list[ReceiptItem]
    total: Decimal
    purchased_at: datetime


@dataclass(frozen=True)
class BudgetSummary:
    month: str
    budget: Decimal | None
    spent: Decimal
    receipts_count: int
    top_items: list[tuple[str, int]]

    @property
    def remaining(self) -> Decimal | None:
        if self.budget is None:
            return None
        return self.budget - self.spent


class SpendingStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def add_receipt(
        self,
        *,
        user_id: int,
        store: str,
        items: list[ReceiptItem],
        purchased_at: datetime | None = None,
    ) -> Receipt:
        if not items:
            raise ValueError("receipt has no items")
        receipt = Receipt(
            id=secrets.token_hex(4),
            user_id=user_id,
            store=store.strip() or "unknown",
            items=items,
            total=sum((item.price for item in items), Decimal("0")),
            purchased_at=(purchased_at or datetime.now(UTC)).astimezone(UTC),
        )
        receipts = self.list_receipts(user_id=user_id, limit=1000)
        receipts.append(receipt)
        self._write_receipts(user_id=user_id, receipts=receipts[-1000:])
        return receipt

    def list_receipts(self, *, user_id: int, limit: int = 20) -> list[Receipt]:
        path = self._receipts_path(user_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        receipts = [_receipt_from_dict(item) for item in raw]
        receipts.sort(key=lambda receipt: receipt.purchased_at, reverse=True)
        return receipts[:limit]

    def set_budget(self, *, user_id: int, month: str, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("budget must be positive")
        budgets = self._read_budgets(user_id)
        budgets[month] = str(amount)
        path = self._budgets_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(budgets, ensure_ascii=False, indent=2), encoding="utf-8")

    def budget_summary(self, *, user_id: int, month: str | None = None) -> BudgetSummary:
        effective_month = month or datetime.now(UTC).strftime("%Y-%m")
        receipts = [
            receipt
            for receipt in self.list_receipts(user_id=user_id, limit=1000)
            if receipt.purchased_at.strftime("%Y-%m") == effective_month
        ]
        spent = sum((receipt.total for receipt in receipts), Decimal("0"))
        budgets = self._read_budgets(user_id)
        budget = Decimal(budgets[effective_month]) if effective_month in budgets else None
        counts: Counter[str] = Counter()
        for receipt in receipts:
            counts.update(item.name for item in receipt.items)
        return BudgetSummary(
            month=effective_month,
            budget=budget,
            spent=spent,
            receipts_count=len(receipts),
            top_items=counts.most_common(5),
        )

    def _write_receipts(self, *, user_id: int, receipts: list[Receipt]) -> None:
        path = self._receipts_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                [_receipt_to_dict(receipt) for receipt in receipts],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _read_budgets(self, user_id: int) -> dict[str, str]:
        path = self._budgets_path(user_id)
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {str(key): str(value) for key, value in raw.items()}

    def _receipts_path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "spending" / "receipts.json"

    def _budgets_path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "spending" / "budgets.json"


def parse_receipt_text(
    text: str,
    *,
    default_store: str = "unknown",
) -> tuple[str, list[ReceiptItem]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("receipt text is empty")
    store = default_store
    if lines[0].lower().startswith(("магазин:", "store:")):
        store = lines.pop(0).partition(":")[2].strip() or default_store
    items: list[ReceiptItem] = []
    for line in lines:
        parsed = _parse_receipt_line(line)
        if parsed is not None:
            items.append(parsed)
    if not items:
        raise ValueError("Не нашёл строки вида: товар 123.45")
    return store, items


def format_receipt(receipt: Receipt) -> str:
    lines = [
        f"Чек сохранён: {receipt.store}",
        f"Итого: {_money(receipt.total)}",
        "Товары:",
    ]
    lines.extend(f"- {item.name}: {_money(item.price)}" for item in receipt.items[:12])
    if len(receipt.items) > 12:
        lines.append(f"...и ещё {len(receipt.items) - 12}")
    return "\n".join(lines)


def format_budget_summary(summary: BudgetSummary) -> str:
    lines = [
        f"Бюджет {summary.month}",
        f"Потрачено: {_money(summary.spent)}",
        f"Чеков: {summary.receipts_count}",
    ]
    if summary.budget is not None:
        lines.append(f"Лимит: {_money(summary.budget)}")
        lines.append(f"Остаток: {_money(summary.remaining)}")
    else:
        lines.append("Лимит не задан. Используй /budget_set YYYY-MM сумма.")
    if summary.top_items:
        top_items = ", ".join(f"{name}: {count}" for name, count in summary.top_items)
        lines.append("Частые позиции: " + top_items)
    return "\n".join(lines)


def _parse_receipt_line(line: str) -> ReceiptItem | None:
    match = re.search(r"(?P<price>\d+(?:[.,]\d{1,2})?)\s*(?:₽|руб\.?)?\s*$", line)
    if match is None:
        return None
    name = line[: match.start()].strip(" -—\t")
    if not name:
        return None
    price = _decimal(match.group("price"))
    if price <= 0:
        return None
    return ReceiptItem(name=name.lower(), price=price)


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value.replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid decimal") from exc


def _money(value: Decimal | None) -> str:
    if value is None:
        return "не задано"
    return f"{value.quantize(Decimal('0.01'))} ₽"


def _receipt_to_dict(receipt: Receipt) -> dict[str, object]:
    return {
        "id": receipt.id,
        "user_id": receipt.user_id,
        "store": receipt.store,
        "items": [{"name": item.name, "price": str(item.price)} for item in receipt.items],
        "total": str(receipt.total),
        "purchased_at": receipt.purchased_at.isoformat(),
    }


def _receipt_from_dict(raw: dict[str, object]) -> Receipt:
    raw_items = raw.get("items", [])
    if not isinstance(raw_items, list):
        raw_items = []
    items = [
        ReceiptItem(name=str(item["name"]), price=Decimal(str(item["price"])))
        for item in raw_items
        if isinstance(item, dict)
    ]
    purchased_at = datetime.fromisoformat(str(raw["purchased_at"])).astimezone(UTC)
    return Receipt(
        id=str(raw["id"]),
        user_id=int(str(raw["user_id"])),
        store=str(raw["store"]),
        items=items,
        total=Decimal(str(raw["total"])),
        purchased_at=purchased_at,
    )


def current_month(now: date | None = None) -> str:
    current = now or datetime.now(UTC).date()
    return current.strftime("%Y-%m")
