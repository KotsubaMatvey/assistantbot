from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class StandingOrder:
    id: str
    user_id: int
    text: str
    created_at: datetime


class StandingOrderStore:
    def __init__(self, vault_path: str) -> None:
        self.path = Path(vault_path).expanduser() / "standing-orders.json"

    def add_order(
        self,
        *,
        user_id: int,
        text: str,
        now: datetime | None = None,
    ) -> StandingOrder:
        clean = text.strip()
        if not clean:
            raise ValueError("standing order is empty")
        order = StandingOrder(
            id=secrets.token_hex(4),
            user_id=user_id,
            text=clean,
            created_at=(now or datetime.now(UTC)).astimezone(UTC),
        )
        orders = self.list_orders()
        orders.append(order)
        self._write_orders(orders)
        return order

    def list_orders(self, *, user_id: int | None = None) -> list[StandingOrder]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        orders = [_order_from_dict(item) for item in raw]
        if user_id is not None:
            orders = [order for order in orders if order.user_id == user_id]
        orders.sort(key=lambda order: order.created_at)
        return orders

    def delete_order(self, *, user_id: int, order_id: str) -> bool:
        orders = self.list_orders()
        remaining = [
            order for order in orders if not (order.user_id == user_id and order.id == order_id)
        ]
        if len(remaining) == len(orders):
            return False
        self._write_orders(remaining)
        return True

    def _write_orders(self, orders: list[StandingOrder]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([_order_to_dict(order) for order in orders], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _order_to_dict(order: StandingOrder) -> dict[str, object]:
    return {
        "id": order.id,
        "user_id": order.user_id,
        "text": order.text,
        "created_at": order.created_at.isoformat(),
    }


def _order_from_dict(raw: dict[str, object]) -> StandingOrder:
    return StandingOrder(
        id=str(raw["id"]),
        user_id=int(str(raw["user_id"])),
        text=str(raw["text"]),
        created_at=datetime.fromisoformat(str(raw["created_at"])).astimezone(UTC),
    )
