from __future__ import annotations

import json
import re
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.services.basket_parser import parse_basket
from app.services.price_comparator import PriceOffer, compare_prices

CONDITION_BELOW_PRICE = "below_price"
CONDITION_BELOW_AVERAGE = "below_average"
CONDITION_DISCOUNT_PERCENT = "discount_percent"
CONDITION_IN_STOCK = "in_stock"


@dataclass(frozen=True)
class PriceAlert:
    id: str
    user_id: int
    item_text: str
    threshold: Decimal | None = None
    condition: str = CONDITION_BELOW_PRICE
    discount_percent: Decimal | None = None
    enabled: bool = True
    created_at: datetime | None = None


@dataclass(frozen=True)
class PriceAlertSpec:
    item_text: str
    condition: str
    threshold: Decimal | None = None
    discount_percent: Decimal | None = None

    def __iter__(self) -> Iterator[object]:
        yield self.item_text
        yield self.threshold


@dataclass(frozen=True)
class PriceAlertHit:
    alert: PriceAlert
    store_name: str
    price: Decimal
    label: str
    reason: str


class PriceAlertStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def add_alert(
        self,
        *,
        user_id: int,
        item_text: str,
        threshold: Decimal | None = None,
        condition: str = CONDITION_BELOW_PRICE,
        discount_percent: Decimal | None = None,
        now: datetime | None = None,
    ) -> PriceAlert:
        clean_item = item_text.strip()
        if not clean_item:
            raise ValueError("alert item is empty")
        if condition == CONDITION_BELOW_PRICE and (threshold is None or threshold <= 0):
            raise ValueError("threshold must be positive")
        if condition == CONDITION_DISCOUNT_PERCENT and (
            discount_percent is None or discount_percent <= 0
        ):
            raise ValueError("discount percent must be positive")
        alert = PriceAlert(
            id=secrets.token_hex(4),
            user_id=user_id,
            item_text=clean_item,
            threshold=threshold,
            condition=condition,
            discount_percent=discount_percent,
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


def parse_price_alert_request(text: str) -> PriceAlertSpec:
    clean = text.strip()
    if not clean:
        raise ValueError("Использование: /watch_price <товар> <условие>")

    discount = re.search(
        r"(?:скидк[аи]|discount)\s*(?:>=|>|от)?\s*"
        r"(?P<discount>\d+(?:[.,]\d{1,2})?)\s*%?\s*$",
        clean,
        re.IGNORECASE,
    )
    if discount is not None:
        item_text = clean[: discount.start()].strip(" <=->")
        if not item_text:
            raise ValueError("Использование: /watch_price <товар> скидка 20%")
        return PriceAlertSpec(
            item_text=item_text,
            condition=CONDITION_DISCOUNT_PERCENT,
            discount_percent=Decimal(discount.group("discount").replace(",", ".")),
        )

    lowered = clean.lower()
    for marker in ("ниже обычного", "дешевле обычного", "ниже средней", "дешевле среднего"):
        if lowered.endswith(marker):
            item_text = clean[: -len(marker)].strip(" <=->")
            if not item_text:
                raise ValueError("Использование: /watch_price <товар> ниже обычного")
            return PriceAlertSpec(item_text=item_text, condition=CONDITION_BELOW_AVERAGE)

    for marker in ("в наличии", "появится", "появился", "снова в продаже"):
        if lowered.endswith(marker):
            item_text = clean[: -len(marker)].strip(" <=->")
            if not item_text:
                raise ValueError("Использование: /watch_price <товар> в наличии")
            return PriceAlertSpec(item_text=item_text, condition=CONDITION_IN_STOCK)

    match = re.search(
        r"(?:<=|<|до|ниже)?\s*(?P<threshold>\d+(?:[.,]\d{1,2})?)\s*(?:₽|р|руб\.?)?\s*$",
        clean,
        re.IGNORECASE,
    )
    if match is None:
        raise ValueError("Использование: /watch_price <товар> <условие>")
    item_text = clean[: match.start()].strip(" <=")
    if not item_text:
        raise ValueError("Использование: /watch_price <товар> <условие>")
    try:
        threshold = Decimal(match.group("threshold").replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid threshold") from exc
    return PriceAlertSpec(item_text=item_text, condition=CONDITION_BELOW_PRICE, threshold=threshold)


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
        reason = _alert_reason(alert, best)
        if reason is not None:
            hits.append(
                PriceAlertHit(
                    alert=alert,
                    store_name=best.offer.store_product.store.display_name,
                    price=best.effective_price,
                    label=best.price_label,
                    reason=reason,
                )
            )
    return hits


def format_price_alerts(alerts: list[PriceAlert]) -> str:
    if not alerts:
        return "Price alerts пока нет."
    lines = ["Price alerts:"]
    for alert in alerts:
        lines.append(f"- {alert.id}: {format_price_alert_condition(alert)}")
    return "\n".join(lines)


def format_price_alert_hits(hits: list[PriceAlertHit]) -> str:
    if not hits:
        return "Сработавших price alerts сейчас нет."
    lines = ["Сработали price alerts:"]
    for hit in hits:
        lines.append(
            f"- {hit.alert.item_text}: {hit.store_name} — {_money(hit.price)} "
            f"({hit.label}; {hit.reason})"
        )
    return "\n".join(lines)


def format_price_alert_condition(alert: PriceAlert) -> str:
    if alert.condition == CONDITION_BELOW_AVERAGE:
        return f"{alert.item_text} дешевле обычного"
    if alert.condition == CONDITION_DISCOUNT_PERCENT:
        return f"{alert.item_text} скидка от {alert.discount_percent}%"
    if alert.condition == CONDITION_IN_STOCK:
        return f"{alert.item_text} в наличии"
    return f"{alert.item_text} <= {_money(alert.threshold)}"


def _alert_reason(alert: PriceAlert, best: Any) -> str | None:
    if alert.condition == CONDITION_BELOW_AVERAGE:
        if best.price_delta_percent is not None and best.price_delta_percent <= Decimal("-5"):
            return f"{best.price_trend_label}, {best.price_delta_percent}% к средней"
        return None
    if alert.condition == CONDITION_DISCOUNT_PERCENT:
        discount = _discount_percent(
            best.offer.regular_price or best.offer.old_price,
            best.effective_price,
        )
        if discount is not None and alert.discount_percent is not None:
            if discount >= alert.discount_percent:
                return f"скидка {discount}%"
        return None
    if alert.condition == CONDITION_IN_STOCK:
        if best.offer.in_stock is not False:
            return "товар найден в наличии"
        return None
    if alert.threshold is not None and best.effective_price <= alert.threshold:
        return f"порог {_money(alert.threshold)}"
    return None


def _discount_percent(reference_price: Decimal | None, price: Decimal) -> Decimal | None:
    if reference_price is None or reference_price <= 0 or price >= reference_price:
        return None
    return ((reference_price - price) / reference_price * Decimal("100")).quantize(
        Decimal("0.1")
    )


def _money(value: Decimal | None) -> str:
    if value is None:
        return "нет порога"
    return f"{value.quantize(Decimal('0.01'))} ₽"


def _alert_to_dict(alert: PriceAlert) -> dict[str, object]:
    return {
        "id": alert.id,
        "user_id": alert.user_id,
        "item_text": alert.item_text,
        "threshold": str(alert.threshold) if alert.threshold is not None else None,
        "condition": alert.condition,
        "discount_percent": (
            str(alert.discount_percent) if alert.discount_percent is not None else None
        ),
        "enabled": alert.enabled,
        "created_at": (alert.created_at or datetime.now(UTC)).isoformat(),
    }


def _alert_from_dict(raw: dict[str, object]) -> PriceAlert:
    return PriceAlert(
        id=str(raw["id"]),
        user_id=int(str(raw["user_id"])),
        item_text=str(raw["item_text"]),
        threshold=(
            Decimal(str(raw["threshold"]))
            if raw.get("threshold") is not None
            else None
        ),
        condition=str(raw.get("condition", CONDITION_BELOW_PRICE)),
        discount_percent=(
            Decimal(str(raw["discount_percent"]))
            if raw.get("discount_percent") is not None
            else None
        ),
        enabled=bool(raw.get("enabled", True)),
        created_at=datetime.fromisoformat(str(raw["created_at"])).astimezone(UTC),
    )
