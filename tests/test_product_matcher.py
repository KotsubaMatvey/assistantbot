from __future__ import annotations

from decimal import Decimal

from app.services.basket_parser import parse_basket
from app.services.price_comparator import ProductInfo, StoreInfo
from app.services.product_matcher import match_products, score_match


def product(title: str, quantity: Decimal | None = None, unit: str | None = None) -> ProductInfo:
    return ProductInfo(
        id=1,
        store=StoreInfo(slug="smart", display_name="Smart"),
        raw_title=title,
        normalized_title=title.lower(),
        brand=None,
        category=None,
        quantity_value=quantity,
        quantity_unit=unit,
    )


def test_exact_match() -> None:
    item = parse_basket("молоко 2.5 1 л")[0]
    matches = match_products(item, [product("молоко 2.5 1 л", Decimal("1000"), "мл")])
    assert matches[0].match_type in {"exact", "strong"}


def test_similar_match() -> None:
    item = parse_basket("бананы 1 кг")[0]
    matches = match_products(item, [product("бананы весовые", Decimal("1000"), "г")], mode="similar")
    assert matches[0].match_type == "similar"


def test_different_fat_penalty() -> None:
    item = parse_basket("молоко 2.5 1 л")[0]
    lower, _ = score_match(item, product("молоко 3.2 1 л", Decimal("1000"), "мл"))
    higher, _ = score_match(item, product("молоко 2.5 1 л", Decimal("1000"), "мл"))
    assert lower < higher


def test_different_quantity_penalty() -> None:
    item = parse_basket("кофе 95 г")[0]
    score, _ = score_match(item, product("кофе 250 г", Decimal("250"), "г"))
    assert score < 35
