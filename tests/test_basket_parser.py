from __future__ import annotations

from decimal import Decimal

from app.services.basket_parser import parse_basket


def test_parse_lines_with_units_and_fat() -> None:
    items = parse_basket("молоко 2.5 1 л\nкофе растворимый 95 г")
    assert items[0].name == "молоко"
    assert items[0].quantity_value == Decimal("1000.000")
    assert items[0].quantity_unit == "мл"
    assert items[0].attributes["fat_percent"] == Decimal("2.5")
    assert items[1].quantity_value == Decimal("95.000")
    assert items[1].quantity_unit == "г"


def test_parse_commas_and_semicolons() -> None:
    items = parse_basket("молоко, яйца; сахар, кофе")
    assert [item.name for item in items] == ["молоко", "яйца", "сахар", "кофе"]


def test_parse_eggs_grade_and_count() -> None:
    item = parse_basket("яйца C1 10 шт")[0]
    assert item.name == "яйца c1"
    assert item.quantity_value == Decimal("10.000")
    assert item.quantity_unit == "шт"
    assert item.attributes["grade"] == "C1"


def test_parse_purchase_multiplier_without_polluting_search_text() -> None:
    item = parse_basket("2x молоко 2.5 1 л")[0]

    assert item.name == "молоко"
    assert item.purchase_count == Decimal("2")
    assert item.attributes["search_text"] == "молоко 2.5 1 л"
