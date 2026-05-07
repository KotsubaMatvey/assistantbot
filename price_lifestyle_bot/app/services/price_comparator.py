from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.db.models import PriceType
from app.services.basket_parser import BasketItemParsed
from app.services.loyalty import user_has_store_card
from app.services.product_matcher import MatchableProduct, MatchResult, match_products


@dataclass(frozen=True)
class StoreInfo:
    slug: str
    display_name: str


@dataclass(frozen=True)
class ProductInfo:
    id: int
    store: StoreInfo
    raw_title: str
    normalized_title: str
    brand: str | None = None
    category: str | None = None
    quantity_value: Decimal | None = None
    quantity_unit: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class PriceOffer:
    store_product: ProductInfo
    regular_price: Decimal | None
    old_price: Decimal | None
    promo_price: Decimal | None
    card_price: Decimal | None
    final_price: Decimal
    price_type: PriceType | str
    unit_price: Decimal | None
    unit_price_unit: str | None
    in_stock: bool | None
    scraped_at: datetime


@dataclass(frozen=True)
class ComparedOffer:
    offer: PriceOffer
    match: MatchResult
    effective_price: Decimal
    price_label: str
    used_card: bool
    is_stale: bool


@dataclass(frozen=True)
class PerItemBest:
    item: BasketItemParsed
    offers: list[ComparedOffer]
    weak_matches: list[ComparedOffer] = field(default_factory=list)


@dataclass(frozen=True)
class StoreBasketTotal:
    store: StoreInfo
    total_price: Decimal
    found_items_count: int
    missing_items_count: int
    card_items_count: int
    promo_items_count: int
    notes: list[str]


@dataclass(frozen=True)
class SplitBasket:
    picks: list[tuple[BasketItemParsed, ComparedOffer]]
    total_price: Decimal
    number_of_stores: int
    estimated_savings_vs_best_single_store: Decimal | None


@dataclass(frozen=True)
class PriceComparisonResult:
    per_item_best: list[PerItemBest]
    one_store_basket: list[StoreBasketTotal]
    split_basket: SplitBasket
    unavailable_stores: list[str] = field(default_factory=list)
    stale_stores: list[str] = field(default_factory=list)


def offer_from_snapshot(snapshot: Any) -> PriceOffer:
    store_product = snapshot.store_product
    store = store_product.store
    return PriceOffer(
        store_product=ProductInfo(
            id=store_product.id,
            store=StoreInfo(slug=store.slug, display_name=store.display_name),
            raw_title=store_product.raw_title,
            normalized_title=store_product.normalized_title,
            brand=store_product.brand,
            category=store_product.category,
            quantity_value=store_product.quantity_value,
            quantity_unit=store_product.quantity_unit,
            source_url=store_product.source_url,
        ),
        regular_price=snapshot.regular_price,
        old_price=snapshot.old_price,
        promo_price=snapshot.promo_price,
        card_price=snapshot.card_price,
        final_price=snapshot.final_price,
        price_type=snapshot.price_type,
        unit_price=snapshot.unit_price,
        unit_price_unit=snapshot.unit_price_unit,
        in_stock=snapshot.in_stock,
        scraped_at=snapshot.scraped_at,
    )


def _effective_price(offer: PriceOffer, settings: Any) -> tuple[Decimal, str, bool]:
    store_slug = offer.store_product.store.slug
    has_card = user_has_store_card(settings, store_slug)
    base_price = offer.promo_price or offer.regular_price or offer.final_price
    price_type = str(
        offer.price_type.value if hasattr(offer.price_type, "value") else offer.price_type
    )

    if offer.card_price is not None and has_card:
        label = "по карте"
        if offer.promo_price is not None:
            label = "акция по карте"
        return offer.card_price, label, True

    if offer.card_price is not None and base_price != offer.card_price:
        label = f"{offer.card_price} по карте / {base_price} без карты"
        return base_price, label, False

    if offer.card_price is not None and base_price == offer.card_price:
        return offer.card_price, "только цена по карте", has_card is True
    if price_type == "promo" or offer.promo_price is not None:
        return base_price, "акция", False
    if price_type == "promo_card":
        return base_price, "акция/карта", False
    if price_type == "card":
        return base_price, "по карте", False
    return base_price, "обычная", False


def _is_stale(scraped_at: datetime, freshness_hours: int) -> bool:
    aware = scraped_at if scraped_at.tzinfo else scraped_at.replace(tzinfo=UTC)
    return aware < datetime.now(UTC) - timedelta(hours=freshness_hours)


def _compared_offer(
    offer: PriceOffer,
    match: MatchResult,
    settings: Any,
    freshness_hours: int,
) -> ComparedOffer:
    effective, label, used_card = _effective_price(offer, settings)
    return ComparedOffer(
        offer=offer,
        match=match,
        effective_price=effective,
        price_label=label,
        used_card=used_card,
        is_stale=_is_stale(offer.scraped_at, freshness_hours),
    )


def compare_prices(
    items: list[BasketItemParsed],
    settings: Any,
    offers: list[PriceOffer],
    *,
    freshness_hours: int = 24,
) -> PriceComparisonResult:
    enabled_slugs = set(getattr(settings, "enabled_store_slugs", []) or [])
    filtered = [
        offer
        for offer in offers
        if not enabled_slugs or offer.store_product.store.slug in enabled_slugs
        if offer.in_stock is not False
    ]
    products: list[MatchableProduct] = [offer.store_product for offer in filtered]
    offers_by_product_id = {offer.store_product.id: offer for offer in filtered}
    mode = str(getattr(settings, "comparison_mode", "mixed"))

    per_item: list[PerItemBest] = []
    for item in items:
        matches = match_products(item, products, mode=mode)
        compared = [
            _compared_offer(
                offers_by_product_id[match.store_product.id],
                match,
                settings,
                freshness_hours,
            )
            for match in matches
        ]
        strong = [offer for offer in compared if offer.match.match_type != "weak"]
        weak = [offer for offer in compared if offer.match.match_type == "weak"]
        strong.sort(key=lambda compared_offer: compared_offer.effective_price)
        per_item.append(PerItemBest(item=item, offers=strong, weak_matches=weak))

    one_store = _build_one_store_basket(per_item)
    split = _build_split_basket(per_item, one_store)
    return PriceComparisonResult(
        per_item_best=per_item,
        one_store_basket=one_store,
        split_basket=split,
    )


def _build_one_store_basket(per_item: list[PerItemBest]) -> list[StoreBasketTotal]:
    store_infos: dict[str, StoreInfo] = {}
    for per in per_item:
        for compared in per.offers:
            slug = compared.offer.store_product.store.slug
            store_infos[slug] = compared.offer.store_product.store

    totals: list[StoreBasketTotal] = []
    for slug, store in store_infos.items():
        total = Decimal("0")
        found = 0
        card_count = 0
        promo_count = 0
        notes: list[str] = []
        for per in per_item:
            store_offers = [
                offer for offer in per.offers if offer.offer.store_product.store.slug == slug
            ]
            if not store_offers:
                notes.append(f"не найден: {per.item.name}")
                continue
            best = min(store_offers, key=lambda offer: offer.effective_price)
            total += best.effective_price * per.item.purchase_count
            found += 1
            card_count += int(best.used_card)
            promo_count += int("акция" in best.price_label)
        totals.append(
            StoreBasketTotal(
                store=store,
                total_price=total,
                found_items_count=found,
                missing_items_count=len(per_item) - found,
                card_items_count=card_count,
                promo_items_count=promo_count,
                notes=notes,
            )
        )
    totals.sort(key=lambda total: (total.missing_items_count, total.total_price))
    return totals


def _build_split_basket(
    per_item: list[PerItemBest],
    one_store: list[StoreBasketTotal],
) -> SplitBasket:
    picks: list[tuple[BasketItemParsed, ComparedOffer]] = []
    total = Decimal("0")
    stores: set[str] = set()
    for per in per_item:
        if not per.offers:
            continue
        best = min(per.offers, key=lambda offer: offer.effective_price)
        picks.append((per.item, best))
        total += best.effective_price * per.item.purchase_count
        stores.add(best.offer.store_product.store.slug)
    best_single = next((store for store in one_store if store.missing_items_count == 0), None)
    savings = best_single.total_price - total if best_single is not None else None
    return SplitBasket(
        picks=picks,
        total_price=total,
        number_of_stores=len(stores),
        estimated_savings_vs_best_single_store=savings,
    )
