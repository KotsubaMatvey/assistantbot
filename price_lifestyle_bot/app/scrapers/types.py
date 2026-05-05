from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.db.models import PriceType


class ScrapedProduct(BaseModel):
    external_id: str | None = None
    title: str
    source_url: str | None = None
    regular_price: Decimal | None = None
    old_price: Decimal | None = None
    promo_price: Decimal | None = None
    card_price: Decimal | None = None
    final_price: Decimal
    price_type: PriceType = PriceType.unknown
    currency: str = "RUB"
    category: str | None = None
    brand: str | None = None
    quantity_value: Decimal | None = None
    quantity_unit: str | None = None
    unit_price: Decimal | None = None
    unit_price_unit: str | None = None
    in_stock: bool | None = None
    raw_payload: dict[str, Any] = {}

    model_config = ConfigDict(arbitrary_types_allowed=True)

