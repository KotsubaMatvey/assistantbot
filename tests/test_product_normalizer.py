from __future__ import annotations

from decimal import Decimal

from app.services.product_normalizer import calculate_unit_price, clean_text, normalize_product_text


def test_clean_text_replaces_yo_and_spaces() -> None:
    assert clean_text("  Сгущёнка!!!   1кг ") == "сгущенка 1 кг"


def test_normalize_kg_to_grams() -> None:
    normalized = normalize_product_text("сахар 0.9 кг")
    assert normalized.quantity_value == Decimal("900.000")
    assert normalized.quantity_unit == "г"


def test_normalize_liters_to_milliliters() -> None:
    normalized = normalize_product_text("молоко 0.95 л")
    assert normalized.quantity_value == Decimal("950.000")
    assert normalized.quantity_unit == "мл"


def test_calculate_unit_price() -> None:
    assert calculate_unit_price(Decimal("90"), Decimal("900"), "г") == (
        Decimal("100.00"),
        "руб/кг",
    )
    assert calculate_unit_price(Decimal("50"), Decimal("500"), "мл") == (
        Decimal("100.00"),
        "руб/л",
    )

