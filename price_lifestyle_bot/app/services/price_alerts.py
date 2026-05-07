from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.services.basket_parser import parse_basket
from app.services.price_comparator import PriceOffer, compare_prices


@dataclass(frozen=True)
class PriceAlert:
    id: str
    user_id: int
    item_text: str
    threshold: Decimal
    enabled: bool = True
    created_at: datetime | None = None


@dataclass(frozen=True)
class PriceAlertHit:
    alert: PriceAlert
    store_name: str
    price: Decimal
    label: str


class PriceAlertStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def add_alert(
        self,
        *,
        user_id: int,
        item_text: str,
        threshold: Decimal,
        now: datetime | None = None,
    ) -> PriceAlert:
        clean_item = item_text.strip()
        if not clean_item:
            raise ValueError("alert item is empty")
        if threshold <= 0:
            raise ValueError("threshold must be positive")
        alert = PriceAlert(
            id=secrets.token_hex(4),
            user_id=user_id,
            item_text=clean_item,
            threshold=threshold,
            created_at=(now or datetime.now(UTC)).astimezone(UTC),
        )
        alerts = self.list_alerts(user_id=user_id)
        alerts.append(alert)
        self._write_alerts(user_id=user_id, alerts=alerts)
        return alert

    def list_alerts(self, *, user_id: int) -> list[PriceAlert]:
        path = self._path(user_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        alerts = [_alert_from_dict(item) for item in raw]
        return [alert for alert in alerts if alert.enabled]

    def delete_alert(self, *, user_id: int, alert_id: str) -> bool:
        all_alerts = self._list_all_alerts(user_id=user_id)
        remaining = [alert for alert in all_alerts if alert.id != alert_id]
        if len(remaining) == len(all_alerts):
            return False
        self._write_alerts(user_id=user_id, alerts=remaining)
        return True

    def _list_all_alerts(self, *, user_id: int) -> list[PriceAlert]:
        path = self._path(user_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [_alert_from_dict(item) for item in raw]

    def _write_alerts(self, *, user_id: int, alerts: list[PriceAlert]) -> None:
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([_alert_to_dict(alert) for alert in alerts], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "price-alerts.json"


def parse_price_alert_request(text: str) -> tuple[str, Decimal]:
    clean = text.strip()
    match = re.search(r"(?:<=|<)?\s*(?P<threshold>\d+(?:[.,]\d{1,2})?)\s*$", clean)
    if match is None:
        raise ValueError("Использование: /watch_price <товар> <цена>")
    item_text = clean[: match.start()].strip(" <=")
    if not item_text:
        raise ValueError("Использование: /watch_price <товар> <цена>")
    try:
        threshold = Decimal(match.group("threshold").replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid threshold") from exc
    return item_text, threshold


def evaluate_price_alerts(
    alerts: list[PriceAlert],
    *,
    settings: Any,
    offers: list[PriceOffer],
    freshness_hours: int,
) -> list[PriceAlertHit]:
    hits: list[PriceAlertHit] = []
    for alert in alerts:
        items = parse_basket(alert.item_text)
        if not items:
            continue
        result = compare_prices(
            items[:1],
            settings,
            offers,
            freshness_hours=freshness_hours,
        )
        if not result.per_item_best or not result.per_item_best[0].offers:
            continue
        best = result.per_item_best[0].offers[0]
        if best.effective_price <= alert.threshold:
            hits.append(
                PriceAlertHit(
                    alert=alert,
                    store_name=best.offer.store_product.store.display_name,
                    price=best.effective_price,
                    label=best.price_label,
                )
            )
    return hits


def format_price_alerts(alerts: list[PriceAlert]) -> str:
    if not alerts:
        return "Price alerts пока нет."
    lines = ["Price alerts:"]
    for alert in alerts:
        lines.append(f"- {alert.id}: {alert.item_text} <= {_money(alert.threshold)}")
    return "\n".join(lines)


def format_price_alert_hits(hits: list[PriceAlertHit]) -> str:
    if not hits:
        return "Сработавших price alerts сейчас нет."
    lines = ["Сработали price alerts:"]
    for hit in hits:
        lines.append(
            f"- {hit.alert.item_text}: {hit.store_name} — {_money(hit.price)} "
            f"({hit.label}), порог {_money(hit.alert.threshold)}"
        )
    return "\n".join(lines)


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))} ₽"


def _alert_to_dict(alert: PriceAlert) -> dict[str, object]:
    return {
        "id": alert.id,
        "user_id": alert.user_id,
        "item_text": alert.item_text,
        "threshold": str(alert.threshold),
        "enabled": alert.enabled,
        "created_at": (alert.created_at or datetime.now(UTC)).isoformat(),
    }


def _alert_from_dict(raw: dict[str, object]) -> PriceAlert:
    return PriceAlert(
        id=str(raw["id"]),
        user_id=int(str(raw["user_id"])),
        item_text=str(raw["item_text"]),
        threshold=Decimal(str(raw["threshold"])),
        enabled=bool(raw.get("enabled", True)),
        created_at=datetime.fromisoformat(str(raw["created_at"])).astimezone(UTC),
    )
