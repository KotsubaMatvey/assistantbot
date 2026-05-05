from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.services.basket_parser import BasketItemParsed
from app.services.product_normalizer import normalize_product_text


class MatchableProduct(Protocol):
    raw_title: str
    normalized_title: str
    brand: str | None
    category: str | None
    quantity_value: Decimal | None
    quantity_unit: str | None


@dataclass(frozen=True)
class MatchResult:
    store_product: MatchableProduct
    score: int
    match_type: str
    explanation: str


IMPORTANT_STOPWORDS = {"молоко", "сыр", "яйца", "кофе", "сахар", "бананы", "масло", "хлеб"}


def _quantity_close(
    left_value: Decimal | None,
    left_unit: str | None,
    right_value: Decimal | None,
    right_unit: str | None,
    tolerance: Decimal = Decimal("0.05"),
) -> bool:
    if left_value is None or right_value is None or left_unit is None or right_unit is None:
        return False
    if left_unit != right_unit or left_value <= 0:
        return False
    diff = abs(left_value - right_value) / left_value
    return diff <= tolerance


def _quantity_very_different(item: BasketItemParsed, product: MatchableProduct) -> bool:
    if item.quantity_value is None or product.quantity_value is None:
        return False
    if item.quantity_unit != product.quantity_unit or item.quantity_value <= 0:
        return True
    return abs(item.quantity_value - product.quantity_value) / item.quantity_value > Decimal("0.25")


def _brand_matches(item: BasketItemParsed, product: MatchableProduct) -> bool:
    brand_candidate = item.attributes.get("brand_candidate")
    if not brand_candidate or not product.brand:
        return False
    return str(brand_candidate).lower() == product.brand.lower()


def _fat_penalty(item: BasketItemParsed, product: MatchableProduct) -> bool:
    item_fat = item.attributes.get("fat_percent")
    if item_fat is None:
        return False
    product_fat = normalize_product_text(product.raw_title).fat_percent
    return product_fat is not None and Decimal(str(item_fat)) != product_fat


def score_match(item: BasketItemParsed, product: MatchableProduct) -> tuple[int, list[str]]:
    item_norm = normalize_product_text(item.raw_text)
    product_norm = normalize_product_text(product.raw_title)
    score = 0
    reasons: list[str] = []

    if item_norm.text == product_norm.text or item.name == product.normalized_title:
        score += 100
        reasons.append("точное название")

    if _brand_matches(item, product):
        score += 30
        reasons.append("бренд совпадает")

    if _quantity_close(
        item.quantity_value, item.quantity_unit, product.quantity_value, product.quantity_unit
    ):
        score += 25
        reasons.append("объем/вес совпадает")

    item_tokens = set(item.name.split()) or item_norm.tokens
    product_tokens = product_norm.tokens
    important = item_tokens & product_tokens
    if important:
        score += min(30, int(30 * len(important) / max(len(item_tokens), 1)))
        reasons.append("ключевые слова совпадают")

    if product.category and product.category.lower() in item_norm.text:
        score += 15
        reasons.append("категория совпадает")

    if _fat_penalty(item, product):
        score -= 40
        reasons.append("другая жирность")

    if _quantity_very_different(item, product):
        score -= 30
        reasons.append("сильно отличается объем/вес")

    return score, reasons


def classify_match(score: int) -> str:
    if score >= 100:
        return "exact"
    if score >= 70:
        return "strong"
    if score >= 35:
        return "similar"
    return "weak"


def match_products(
    item: BasketItemParsed,
    products: list[MatchableProduct],
    *,
    mode: str = "mixed",
    min_results: int = 2,
) -> list[MatchResult]:
    scored: list[MatchResult] = []
    for product in products:
        score, reasons = score_match(item, product)
        match_type = classify_match(score)
        scored.append(
            MatchResult(
                store_product=product,
                score=score,
                match_type=match_type,
                explanation=", ".join(reasons) or "слабое совпадение",
            )
        )
    scored.sort(key=lambda result: result.score, reverse=True)

    if mode == "strict":
        return [result for result in scored if result.match_type in {"exact", "strong"}]
    if mode == "similar":
        return [result for result in scored if result.match_type in {"exact", "strong", "similar"}]

    strict = [result for result in scored if result.match_type in {"exact", "strong"}]
    if len(strict) >= min_results:
        return strict
    return [result for result in scored if result.match_type in {"exact", "strong", "similar"}]

