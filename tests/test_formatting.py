from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.bot.message_utils import split_telegram_text
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


def test_format_includes_purchase_multiplier_subtotal() -> None:
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
        parse_basket("2x молоко 2.5 1 л"),
        SimpleNamespace(
            enabled_store_slugs=["smart"],
            comparison_mode="mixed",
            has_smart_card=False,
        ),
        [
            PriceOffer(
                store_product=product,
                regular_price=Decimal("100"),
                old_price=None,
                promo_price=None,
                card_price=None,
                final_price=Decimal("100"),
                price_type=PriceType.regular,
                unit_price=None,
                unit_price_unit=None,
                in_stock=True,
                scraped_at=datetime.now(UTC),
            )
        ],
    )

    text = format_price_comparison(result)

    assert "× 2" in text
    assert "за 2 шт: 200.00 ₽" in text


def test_split_telegram_text_keeps_chunks_under_limit() -> None:
    chunks = split_telegram_text("a\n" * 20, limit=10)

    assert len(chunks) > 1
    assert all(len(chunk) <= 10 for chunk in chunks)
