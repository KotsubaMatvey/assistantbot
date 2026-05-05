from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

PUNCT_RE = re.compile(r"[^\w\s%.,-]", re.UNICODE)
SPACE_RE = re.compile(r"\s+")
QUANTITY_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>кг|гр|грамм|г|литр|л|мл|шт|упаковка|пачка)\b",
    re.IGNORECASE,
)
FAT_RE = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*%?")
UNIT_ALIASES = {
    "кг": "г",
    "г": "г",
    "гр": "г",
    "грамм": "г",
    "л": "мл",
    "литр": "мл",
    "мл": "мл",
    "шт": "шт",
    "упаковка": "шт",
    "пачка": "шт",
}


@dataclass(frozen=True)
class NormalizedProductText:
    raw_text: str
    text: str
    tokens: set[str]
    quantity_value: Decimal | None
    quantity_unit: str | None
    fat_percent: Decimal | None


def clean_text(value: str) -> str:
    lowered = value.lower().replace("ё", "е")
    without_punct = PUNCT_RE.sub(" ", lowered)
    compact_units = re.sub(r"(\d)\s*(кг|гр|грамм|г|литр|л|мл|шт)\b", r"\1 \2", without_punct)
    return SPACE_RE.sub(" ", compact_units).strip()


def parse_decimal(value: str) -> Decimal:
    return Decimal(value.replace(",", "."))


def normalize_quantity(value: Decimal, unit: str) -> tuple[Decimal, str]:
    normalized_unit = UNIT_ALIASES[unit.lower()]
    if unit.lower() == "кг":
        value *= Decimal("1000")
    elif unit.lower() in {"л", "литр"}:
        value *= Decimal("1000")
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP), normalized_unit


def extract_quantity(text: str) -> tuple[Decimal | None, str | None]:
    match = QUANTITY_RE.search(text)
    if not match:
        return None, None
    return normalize_quantity(parse_decimal(match.group("value")), match.group("unit"))


def extract_fat_percent(text: str) -> Decimal | None:
    for match in FAT_RE.finditer(text):
        value = parse_decimal(match.group("value"))
        tail = text[match.end() :].lstrip()
        follows_unit = tail.startswith(("кг", "гр", "грамм", "г", "л", "мл", "шт"))
        has_decimal = "." in match.group("value") or "," in match.group("value")
        if "%" in match.group(0) or (has_decimal and value <= 10 and not follows_unit):
            return value.quantize(Decimal("0.1"))
    return None


def normalize_product_text(value: str) -> NormalizedProductText:
    text = clean_text(value)
    quantity_value, quantity_unit = extract_quantity(text)
    tokens = {token for token in text.split() if token not in {"и", "для", "с"}}
    return NormalizedProductText(
        raw_text=value,
        text=text,
        tokens=tokens,
        quantity_value=quantity_value,
        quantity_unit=quantity_unit,
        fat_percent=extract_fat_percent(text),
    )


def build_normalized_key(value: str) -> str:
    normalized = normalize_product_text(value)
    tokens = [token for token in normalized.text.split() if not QUANTITY_RE.fullmatch(token)]
    return " ".join(tokens)


def calculate_unit_price(
    price: Decimal,
    quantity_value: Decimal | None,
    quantity_unit: str | None,
) -> tuple[Decimal | None, str | None]:
    if price <= 0 or quantity_value is None or quantity_value <= 0 or quantity_unit is None:
        return None, None
    if quantity_unit == "г":
        return (price / quantity_value * Decimal("1000")).quantize(Decimal("0.01")), "руб/кг"
    if quantity_unit == "мл":
        return (price / quantity_value * Decimal("1000")).quantize(Decimal("0.01")), "руб/л"
    if quantity_unit == "шт":
        return (price / quantity_value).quantize(Decimal("0.01")), "руб/шт"
    return None, None
