from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.db.models import PriceType
from app.services.basket_parser import parse_basket
from app.services.formatting import PRICE_DISCLAIMER, format_price_comparison
from app.services.price_comparator import PriceOffer, ProductInfo, StoreInfo, compare_prices


def test_format_includes_summary_disclaimer_and_price_type() -> None:
    store = StoreInfo(slug="smart", display_name="Smart")
    product = ProductInfo(
        id=1,
        store=store,
        raw_title="молоко 2.5 1 л",
        normalized_title="молоко 2.5 1 л",
        quantity_value=Decimal("1000"),
        quantity_unit="мл",
    )
    result = compare_prices(
        parse_basket("молоко 2.5 1 л"),
        SimpleNamespace(
            enabled_store_slugs=["smart"],
            comparison_mode="mixed",
            has_smart_card=False,
        ),
        [
            PriceOffer(
                store_product=product,
                regular_price=Decimal("109"),
                old_price=None,
                promo_price=None,
                card_price=Decimal("89"),
                final_price=Decimal("89"),
                price_type=PriceType.card,
                unit_price=None,
                unit_price_unit=None,
                in_stock=True,
                scraped_at=datetime.now(UTC),
            )
        ],
    )
    text = format_price_comparison(result)
    assert "Сравнение корзины" in text
    assert "Лучший один магазин" in text
    assert PRICE_DISCLAIMER in text
    assert "по карте" in text
