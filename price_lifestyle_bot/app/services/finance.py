from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.services.file_io import atomic_write_text


@dataclass(frozen=True)
class FinanceTransaction:
    id: str
    user_id: int
    kind: str
    amount: Decimal
    category: str
    note: str
    account: str
    created_at: datetime


@dataclass(frozen=True)
class FinanceAccount:
    id: str
    user_id: int
    name: str
    balance: Decimal
    currency: str
    updated_at: datetime


@dataclass(frozen=True)
class Subscription:
    id: str
    user_id: int
    name: str
    amount: Decimal
    cycle: str
    enabled: bool
    created_at: datetime


@dataclass(frozen=True)
class CashflowSummary:
    month: str
    balance: Decimal
    income: Decimal
    expenses: Decimal
    receipt_expenses: Decimal
    subscriptions: Decimal
    forecast: Decimal


class FinanceStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def add_transaction(
        self,
        *,
        user_id: int,
        kind: str,
        amount: Decimal,
        category: str,
        note: str = "",
        account: str = "cash",
        created_at: datetime | None = None,
    ) -> FinanceTransaction:
        clean_kind = kind.strip().lower()
        if clean_kind not in {"expense", "income"}:
            raise ValueError("transaction kind must be expense or income")
        if amount <= 0:
            raise ValueError("amount must be positive")
        transaction = FinanceTransaction(
            id=secrets.token_hex(4),
            user_id=user_id,
            kind=clean_kind,
            amount=amount,
            category=category.strip() or "other",
            note=note.strip(),
            account=account.strip() or "cash",
            created_at=(created_at or datetime.now(UTC)).astimezone(UTC),
        )
        transactions = self.list_transactions(user_id=user_id, limit=10_000)
        transactions.append(transaction)
        self._write_transactions(user_id=user_id, transactions=transactions[-10_000:])
        return transaction

    def list_transactions(
        self,
        *,
        user_id: int,
        kind: str | None = None,
        month: str | None = None,
        limit: int = 50,
    ) -> list[FinanceTransaction]:
        path = self._transactions_path(user_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        transactions = [_transaction_from_dict(item) for item in raw if isinstance(item, dict)]
        if kind is not None:
            clean_kind = kind.strip().lower()
            transactions = [item for item in transactions if item.kind == clean_kind]
        if month is not None:
            transactions = [
                item for item in transactions if item.created_at.strftime("%Y-%m") == month
            ]
        transactions.sort(key=lambda item: item.created_at, reverse=True)
        return transactions[:limit]

    def upsert_account(
        self,
        *,
        user_id: int,
        name: str,
        balance: Decimal,
        currency: str = "RUB",
        updated_at: datetime | None = None,
    ) -> FinanceAccount:
        clean_name = " ".join(name.strip().split())
        if not clean_name:
            raise ValueError("account name is empty")
        account = FinanceAccount(
            id=_stable_id("acct", clean_name),
            user_id=user_id,
            name=clean_name,
            balance=balance,
            currency=currency.strip().upper() or "RUB",
            updated_at=(updated_at or datetime.now(UTC)).astimezone(UTC),
        )
        accounts = [
            existing
            for existing in self.list_accounts(user_id=user_id)
            if existing.id != account.id
        ]
        accounts.append(account)
        self._write_accounts(user_id=user_id, accounts=accounts)
        return account

    def list_accounts(self, *, user_id: int) -> list[FinanceAccount]:
        path = self._accounts_path(user_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        accounts = [_account_from_dict(item) for item in raw if isinstance(item, dict)]
        accounts.sort(key=lambda item: item.name.lower())
        return accounts

    def upsert_subscription(
        self,
        *,
        user_id: int,
        name: str,
        amount: Decimal,
        cycle: str = "monthly",
        enabled: bool = True,
        created_at: datetime | None = None,
    ) -> Subscription:
        clean_name = " ".join(name.strip().split())
        if not clean_name:
            raise ValueError("subscription name is empty")
        if amount <= 0:
            raise ValueError("amount must be positive")
        subscription = Subscription(
            id=_stable_id("sub", clean_name),
            user_id=user_id,
            name=clean_name,
            amount=amount,
            cycle=cycle.strip().lower() or "monthly",
            enabled=enabled,
            created_at=(created_at or datetime.now(UTC)).astimezone(UTC),
        )
        subscriptions = [
            existing
            for existing in self.list_subscriptions(user_id=user_id, include_disabled=True)
            if existing.id != subscription.id
        ]
        subscriptions.append(subscription)
        self._write_subscriptions(user_id=user_id, subscriptions=subscriptions)
        return subscription

    def list_subscriptions(
        self,
        *,
        user_id: int,
        include_disabled: bool = False,
    ) -> list[Subscription]:
        path = self._subscriptions_path(user_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        subscriptions = [_subscription_from_dict(item) for item in raw if isinstance(item, dict)]
        if not include_disabled:
            subscriptions = [item for item in subscriptions if item.enabled]
        subscriptions.sort(key=lambda item: item.name.lower())
        return subscriptions

    def cashflow_summary(
        self,
        *,
        user_id: int,
        month: str,
        receipt_expenses: Decimal = Decimal("0"),
    ) -> CashflowSummary:
        transactions = self.list_transactions(user_id=user_id, month=month, limit=10_000)
        income = sum((item.amount for item in transactions if item.kind == "income"), Decimal("0"))
        expenses = sum(
            (item.amount for item in transactions if item.kind == "expense"),
            Decimal("0"),
        )
        balance = sum(
            (account.balance for account in self.list_accounts(user_id=user_id)),
            Decimal("0"),
        )
        subscriptions = sum(
            (_monthly_amount(item) for item in self.list_subscriptions(user_id=user_id)),
            Decimal("0"),
        )
        forecast = balance + income - expenses - receipt_expenses - subscriptions
        return CashflowSummary(
            month=month,
            balance=balance,
            income=income,
            expenses=expenses,
            receipt_expenses=receipt_expenses,
            subscriptions=subscriptions,
            forecast=forecast,
        )

    def _write_transactions(
        self,
        *,
        user_id: int,
        transactions: list[FinanceTransaction],
    ) -> None:
        path = self._transactions_path(user_id)
        atomic_write_text(
            path,
            json.dumps(
                [_transaction_to_dict(item) for item in transactions],
                ensure_ascii=False,
                indent=2,
            ),
        )

    def _write_accounts(self, *, user_id: int, accounts: list[FinanceAccount]) -> None:
        path = self._accounts_path(user_id)
        atomic_write_text(
            path,
            json.dumps([_account_to_dict(item) for item in accounts], ensure_ascii=False, indent=2),
        )

    def _write_subscriptions(
        self,
        *,
        user_id: int,
        subscriptions: list[Subscription],
    ) -> None:
        path = self._subscriptions_path(user_id)
        atomic_write_text(
            path,
            json.dumps(
                [_subscription_to_dict(item) for item in subscriptions],
                ensure_ascii=False,
                indent=2,
            ),
        )

    def _transactions_path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "finance" / "transactions.json"

    def _accounts_path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "finance" / "accounts.json"

    def _subscriptions_path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "finance" / "subscriptions.json"


def parse_amount(value: str) -> Decimal:
    try:
        return Decimal(value.replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("amount must be a number") from exc


def parse_transaction_request(text: str) -> tuple[Decimal, str, str]:
    parts = text.strip().split(maxsplit=2)
    if len(parts) < 2:
        raise ValueError("usage: amount category [note]")
    return parse_amount(parts[0]), parts[1], parts[2] if len(parts) == 3 else ""


def parse_named_amount(text: str) -> tuple[str, Decimal]:
    parts = text.strip().split()
    if len(parts) < 2:
        raise ValueError("usage: name amount")
    amount = parse_amount(parts[-1])
    name = " ".join(parts[:-1])
    return name, amount


def format_transaction(transaction: FinanceTransaction) -> str:
    return "\n".join(
        [
            f"{transaction.kind.title()} saved: {format_money(transaction.amount)}",
            f"Category: {transaction.category}",
            f"Account: {transaction.account}",
            f"ID: {transaction.id}",
        ]
    )


def format_accounts(accounts: list[FinanceAccount]) -> str:
    if not accounts:
        return "Accounts are empty. Use /accounts Cash 10000."
    lines = ["Accounts:"]
    lines.extend(
        f"- {account.name}: {format_money(account.balance)} {account.currency}"
        for account in accounts
    )
    balance = sum((account.balance for account in accounts), Decimal("0"))
    lines.append(f"Balance: {format_money(balance)}")
    return "\n".join(lines)


def format_subscriptions(subscriptions: list[Subscription]) -> str:
    if not subscriptions:
        return "Subscriptions are empty. Use /subscriptions Name 999."
    lines = ["Subscriptions:"]
    lines.extend(
        f"- {item.name}: {format_money(item.amount)} / {item.cycle}"
        for item in subscriptions
    )
    monthly_total = sum((_monthly_amount(item) for item in subscriptions), Decimal("0"))
    lines.append(f"Monthly total: {format_money(monthly_total)}")
    return "\n".join(lines)


def format_cashflow(summary: CashflowSummary) -> str:
    return "\n".join(
        [
            f"Cashflow {summary.month}",
            f"Balance: {format_money(summary.balance)}",
            f"Income: {format_money(summary.income)}",
            f"Expenses: {format_money(summary.expenses)}",
            f"Receipt expenses: {format_money(summary.receipt_expenses)}",
            f"Subscriptions: {format_money(summary.subscriptions)}",
            f"Forecast: {format_money(summary.forecast)}",
        ]
    )


def format_money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))} RUB"


def _monthly_amount(subscription: Subscription) -> Decimal:
    if subscription.cycle == "yearly":
        return (subscription.amount / Decimal("12")).quantize(Decimal("0.01"))
    return subscription.amount


def _stable_id(prefix: str, name: str) -> str:
    return f"{prefix}_{name.strip().lower().replace(' ', '_')[:40]}"


def _transaction_to_dict(transaction: FinanceTransaction) -> dict[str, object]:
    return {
        "id": transaction.id,
        "user_id": transaction.user_id,
        "kind": transaction.kind,
        "amount": str(transaction.amount),
        "category": transaction.category,
        "note": transaction.note,
        "account": transaction.account,
        "created_at": transaction.created_at.isoformat(),
    }


def _account_to_dict(account: FinanceAccount) -> dict[str, object]:
    return {
        "id": account.id,
        "user_id": account.user_id,
        "name": account.name,
        "balance": str(account.balance),
        "currency": account.currency,
        "updated_at": account.updated_at.isoformat(),
    }


def _subscription_to_dict(subscription: Subscription) -> dict[str, object]:
    return {
        "id": subscription.id,
        "user_id": subscription.user_id,
        "name": subscription.name,
        "amount": str(subscription.amount),
        "cycle": subscription.cycle,
        "enabled": subscription.enabled,
        "created_at": subscription.created_at.isoformat(),
    }


def _transaction_from_dict(raw: dict[str, object]) -> FinanceTransaction:
    return FinanceTransaction(
        id=str(raw["id"]),
        user_id=int(str(raw["user_id"])),
        kind=str(raw["kind"]),
        amount=Decimal(str(raw["amount"])),
        category=str(raw["category"]),
        note=str(raw.get("note", "")),
        account=str(raw.get("account", "cash")),
        created_at=_parse_datetime(str(raw["created_at"])),
    )


def _account_from_dict(raw: dict[str, object]) -> FinanceAccount:
    return FinanceAccount(
        id=str(raw["id"]),
        user_id=int(str(raw["user_id"])),
        name=str(raw["name"]),
        balance=Decimal(str(raw["balance"])),
        currency=str(raw.get("currency", "RUB")),
        updated_at=_parse_datetime(str(raw["updated_at"])),
    )


def _subscription_from_dict(raw: dict[str, object]) -> Subscription:
    return Subscription(
        id=str(raw["id"]),
        user_id=int(str(raw["user_id"])),
        name=str(raw["name"]),
        amount=Decimal(str(raw["amount"])),
        cycle=str(raw.get("cycle", "monthly")),
        enabled=bool(raw.get("enabled", True)),
        created_at=_parse_datetime(str(raw["created_at"])),
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
