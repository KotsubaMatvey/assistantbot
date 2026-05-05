from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.services.product_normalizer import extract_fat_percent, extract_quantity, clean_text

SPLIT_RE = re.compile(r"[\n;]+|,\s*(?=[^\d])")
GRADE_RE = re.compile(r"\b[сc]\s?([0-3])\b", re.IGNORECASE)


@dataclass(frozen=True)
class BasketItemParsed:
    raw_text: str
    name: str
    quantity_value: Decimal | None
    quantity_unit: str | None
    attributes: dict[str, object] = field(default_factory=dict)


def _strip_quantity(text: str) -> str:
    return re.sub(
        r"\d+(?:[.,]\d+)?\s*(кг|гр|грамм|г|литр|л|мл|шт|упаковка|пачка)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )


def parse_basket(text: str) -> list[BasketItemParsed]:
    parts = [part.strip() for part in SPLIT_RE.split(text) if part.strip()]
    items: list[BasketItemParsed] = []
    for raw in parts:
        cleaned = clean_text(raw)
        quantity_value, quantity_unit = extract_quantity(cleaned)
        grade_match = GRADE_RE.search(cleaned)
        name = _strip_quantity(cleaned)
        name = re.sub(r"\b\d+(?:[.,]\d+)?\s*%?\b", "", name)
        name = re.sub(r"\s+", " ", name).strip()
        attributes: dict[str, object] = {}
        fat_percent = extract_fat_percent(cleaned)
        if fat_percent is not None:
            attributes["fat_percent"] = fat_percent
        if grade_match is not None:
            attributes["grade"] = f"C{grade_match.group(1)}"
        tokens = cleaned.split()
        if tokens and tokens[0].isalpha() and tokens[0] not in {"молоко", "яйца", "сахар", "кофе"}:
            attributes["brand_candidate"] = tokens[0]
        items.append(
            BasketItemParsed(
                raw_text=raw,
                name=name or cleaned,
                quantity_value=quantity_value,
                quantity_unit=quantity_unit,
                attributes=attributes,
            )
        )
    return items

