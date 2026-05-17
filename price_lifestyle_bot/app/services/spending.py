from __future__ import annotations

import json
import math
import re
import secrets
from calendar import monthrange
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.services.basket_parser import BasketItemParsed
from app.services.file_io import atomic_write_text


@dataclass(frozen=True)
class ReceiptItem:
    name: str
    price: Decimal
    category: str = "прочее"


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
    category_totals: list[tuple[str, Decimal]]
    days_elapsed: int
    days_in_month: int
    projected_spend: Decimal

    @property
    def remaining(self) -> Decimal | None:
        if self.budget is None:
            return None
        return self.budget - self.spent


@dataclass(frozen=True)
class PlanVsActualItem:
    name: str
    actual_count: int
    actual_spent: Decimal


@dataclass(frozen=True)
class PlanVsActual:
    month: str
    planned_items_count: int
    matched: list[PlanVsActualItem]
    missing: list[str]
    unplanned: list[PlanVsActualItem]


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
        atomic_write_text(path, json.dumps(budgets, ensure_ascii=False, indent=2))

    def budget_summary(
        self,
        *,
        user_id: int,
        month: str | None = None,
        now: date | None = None,
    ) -> BudgetSummary:
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
        category_totals: dict[str, Decimal] = {}
        for receipt in receipts:
            counts.update(item.name for item in receipt.items)
            for item in receipt.items:
                category_totals[item.category] = (
                    category_totals.get(item.category, Decimal("0")) + item.price
                )
        days_elapsed, days_in_month = _month_progress(effective_month, now=now)
        projected = _project_spend(spent, days_elapsed=days_elapsed, days_in_month=days_in_month)
        return BudgetSummary(
            month=effective_month,
            budget=budget,
            spent=spent,
            receipts_count=len(receipts),
            top_items=counts.most_common(5),
            category_totals=sorted(
                category_totals.items(),
                key=lambda item: item[1],
                reverse=True,
            ),
            days_elapsed=days_elapsed,
            days_in_month=days_in_month,
            projected_spend=projected,
        )

    def plan_vs_actual(
        self,
        *,
        user_id: int,
        planned_items: list[BasketItemParsed],
        month: str | None = None,
    ) -> PlanVsActual:
        effective_month = month or datetime.now(UTC).strftime("%Y-%m")
        receipts = [
            receipt
            for receipt in self.list_receipts(user_id=user_id, limit=1000)
            if receipt.purchased_at.strftime("%Y-%m") == effective_month
        ]
        receipt_items = [item for receipt in receipts for item in receipt.items]
        actual_by_plan: dict[str, list[ReceiptItem]] = {}
        planned_names = [item.name for item in planned_items]
        for planned_name in planned_names:
            actual_by_plan[planned_name] = [
                item for item in receipt_items if _names_match(planned_name, item.name)
            ]
        matched = [
            PlanVsActualItem(
                name=name,
                actual_count=len(items),
                actual_spent=sum((item.price for item in items), Decimal("0")),
            )
            for name, items in actual_by_plan.items()
            if items
        ]
        missing = [name for name, items in actual_by_plan.items() if not items]
        unplanned = [
            PlanVsActualItem(name=item.name, actual_count=count, actual_spent=amount)
            for item, count, amount in _unplanned_receipt_items(receipt_items, planned_names)
        ]
        return PlanVsActual(
            month=effective_month,
            planned_items_count=len(planned_items),
            matched=matched,
            missing=missing,
            unplanned=unplanned,
        )

    def _write_receipts(self, *, user_id: int, receipts: list[Receipt]) -> None:
        path = self._receipts_path(user_id)
        atomic_write_text(
            path,
            json.dumps(
                [_receipt_to_dict(receipt) for receipt in receipts],
                ensure_ascii=False,
                indent=2,
            ),
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
    lines.extend(
        f"- {item.name}: {_money(item.price)} ({item.category})" for item in receipt.items[:12]
    )
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
        lines.append(f"Прогноз месяца: {_money(summary.projected_spend)}")
        if summary.projected_spend > summary.budget:
            lines.append(
                "Риск перерасхода: "
                f"{_money(summary.projected_spend - summary.budget)} к концу месяца"
            )
    else:
        lines.append("Лимит не задан. Используй /budget_set YYYY-MM сумма.")
        lines.append(f"Прогноз месяца: {_money(summary.projected_spend)}")
    if summary.category_totals:
        categories = ", ".join(
            f"{category}: {_money(amount)}" for category, amount in summary.category_totals[:5]
        )
        lines.append("Категории: " + categories)
    if summary.top_items:
        top_items = ", ".join(f"{name}: {count}" for name, count in summary.top_items)
        lines.append("Частые позиции: " + top_items)
    return "\n".join(lines)


def format_plan_vs_actual(report: PlanVsActual) -> str:
    lines = [
        f"План против факта {report.month}",
        f"В плане: {report.planned_items_count}",
        f"Куплено из плана: {len(report.matched)}",
        f"Не найдено в чеках: {len(report.missing)}",
    ]
    if report.matched:
        lines.append("Совпало:")
        lines.extend(
            f"- {item.name}: {item.actual_count} чек(а), {_money(item.actual_spent)}"
            for item in report.matched[:8]
        )
    if report.missing:
        lines.append("Не пробилось по чекам:")
        lines.extend(f"- {name}" for name in report.missing[:8])
    if report.unplanned:
        lines.append("Вне плана:")
        lines.extend(
            f"- {item.name}: {item.actual_count} раз, {_money(item.actual_spent)}"
            for item in report.unplanned[:8]
        )
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
    clean_name = name.lower()
    return ReceiptItem(name=clean_name, price=price, category=categorize_item(clean_name))


def categorize_item(name: str) -> str:
    text = name.lower()
    category_keywords = {
        "молочные": ("молоко", "кефир", "творог", "йогурт", "сыр", "сметана", "сливки"),
        "хлеб": ("хлеб", "батон", "лаваш", "булк"),
        "яйца": ("яйц",),
        "крупы и сахар": ("сахар", "рис", "греч", "макарон", "мука", "круп"),
        "овощи и фрукты": (
            "банан",
            "яблок",
            "карто",
            "томат",
            "помид",
            "огур",
            "лук",
            "морков",
        ),
        "мясо и рыба": ("кур", "говя", "свин", "фарш", "рыб", "лосос", "колбас", "сосиск"),
        "напитки": ("кофе", "чай", "сок", "вода", "лимонад"),
        "быт": ("порош", "средство", "мыло", "шампун", "бумага", "пакет"),
    }
    for category, keywords in category_keywords.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "прочее"


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value.replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid decimal") from exc


def _money(value: Decimal | None) -> str:
    if value is None:
        return "не задано"
    return f"{value.quantize(Decimal('0.01'))} ₽"


def _month_progress(month: str, *, now: date | None) -> tuple[int, int]:
    year_text, month_text = month.split("-", maxsplit=1)
    year = int(year_text)
    month_number = int(month_text)
    days_in_month = monthrange(year, month_number)[1]
    current = now or datetime.now(UTC).date()
    if current.strftime("%Y-%m") == month:
        return max(1, current.day), days_in_month
    month_end = date(year, month_number, days_in_month)
    if current > month_end:
        return days_in_month, days_in_month
    return 1, days_in_month


def _project_spend(spent: Decimal, *, days_elapsed: int, days_in_month: int) -> Decimal:
    if spent <= 0:
        return Decimal("0")
    daily = spent / Decimal(max(days_elapsed, 1))
    return (daily * Decimal(days_in_month)).quantize(Decimal("0.01"))


def _names_match(left: str, right: str) -> bool:
    left_tokens = _name_tokens(left)
    right_tokens = _name_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = left_tokens & right_tokens
    return bool(overlap) and len(overlap) >= math.ceil(min(len(left_tokens), len(right_tokens)) / 2)


def _name_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[а-яa-z0-9]+", value.lower().replace("ё", "е"))
        if token not in {"и", "для", "с", "шт", "кг", "г", "л", "мл"}
    }


def _unplanned_receipt_items(
    receipt_items: list[ReceiptItem],
    planned_names: list[str],
) -> list[tuple[ReceiptItem, int, Decimal]]:
    grouped: dict[str, tuple[ReceiptItem, int, Decimal]] = {}
    for item in receipt_items:
        if any(_names_match(planned_name, item.name) for planned_name in planned_names):
            continue
        existing = grouped.get(item.name)
        if existing is None:
            grouped[item.name] = (item, 1, item.price)
        else:
            grouped[item.name] = (item, existing[1] + 1, existing[2] + item.price)
    return sorted(grouped.values(), key=lambda row: row[2], reverse=True)


def _receipt_to_dict(receipt: Receipt) -> dict[str, object]:
    return {
        "id": receipt.id,
        "user_id": receipt.user_id,
        "store": receipt.store,
        "items": [
            {"name": item.name, "price": str(item.price), "category": item.category}
            for item in receipt.items
        ],
        "total": str(receipt.total),
        "purchased_at": receipt.purchased_at.isoformat(),
    }


def _receipt_from_dict(raw: dict[str, object]) -> Receipt:
    raw_items = raw.get("items", [])
    if not isinstance(raw_items, list):
        raw_items = []
    items = [
        ReceiptItem(
            name=str(item["name"]),
            price=Decimal(str(item["price"])),
            category=str(item.get("category") or categorize_item(str(item["name"]))),
        )
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
