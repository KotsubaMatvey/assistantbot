from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.db.models import PriceType
from app.services.basket_parser import parse_basket
from app.services.price_comparator import PriceOffer, ProductInfo, StoreInfo, compare_prices


def offer(
    store_slug: str,
    title: str,
    price: str,
    *,
    product_id: int,
    promo: str | None = None,
    card: str | None = None,
    in_stock: bool | None = True,
) -> PriceOffer:
    store = StoreInfo(slug=store_slug, display_name=store_slug.title())
    product = ProductInfo(
        id=product_id,
        store=store,
        raw_title=title,
        normalized_title=title.lower(),
        quantity_value=Decimal("1000"),
        quantity_unit="мл" if "молоко" in title else "г",
    )
    return PriceOffer(
        store_product=product,
        regular_price=Decimal(price),
        old_price=None,
        promo_price=Decimal(promo) if promo else None,
        card_price=Decimal(card) if card else None,
        final_price=Decimal(card or promo or price),
        price_type=PriceType.card if card else PriceType.promo if promo else PriceType.regular,
        unit_price=None,
        unit_price_unit=None,
        in_stock=in_stock,
        scraped_at=datetime.now(UTC),
    )


def settings(**cards: bool) -> SimpleNamespace:
    return SimpleNamespace(
        enabled_store_slugs=["smart", "magnit"],
        comparison_mode="mixed",
        has_smart_card=cards.get("smart", False),
        has_magnit_card=cards.get("magnit", False),
    )


def test_card_price_used_only_when_user_has_card() -> None:
    items = parse_basket("молоко 2.5 1 л")
    offers = [
        offer("smart", "молоко 2.5 1 л", "100", product_id=1, card="80"),
        offer("magnit", "молоко 2.5 1 л", "90", product_id=2),
    ]
    no_card = compare_prices(items, settings(), offers)
    with_card = compare_prices(items, settings(smart=True), offers)
    assert no_card.per_item_best[0].offers[0].offer.store_product.store.slug == "magnit"
    assert with_card.per_item_best[0].offers[0].offer.store_product.store.slug == "smart"


def test_promo_missing_one_store_and_split() -> None:
    items = parse_basket("молоко 2.5 1 л\nсахар 1 кг")
    offers = [
        offer("smart", "молоко 2.5 1 л", "100", product_id=1),
        offer("magnit", "молоко 2.5 1 л", "95", product_id=2, promo="90"),
        offer("magnit", "сахар 1 кг", "70", product_id=3),
    ]
    result = compare_prices(items, settings(), offers)
    assert result.one_store_basket[0].store.slug == "magnit"
    assert result.one_store_basket[0].found_items_count == 2
    assert result.split_basket.total_price == Decimal("160")


def test_purchase_count_multiplies_totals_and_out_of_stock_is_ignored() -> None:
    items = parse_basket("2x молоко 2.5 1 л")
    offers = [
        offer("smart", "молоко 2.5 1 л", "80", product_id=1, in_stock=False),
        offer("magnit", "молоко 2.5 1 л", "90", product_id=2),
    ]

    result = compare_prices(items, settings(), offers)

    assert result.per_item_best[0].offers[0].offer.store_product.store.slug == "magnit"
    assert result.one_store_basket[0].total_price == Decimal("180")
    assert result.split_basket.total_price == Decimal("180")
