from __future__ import annotations

from decimal import Decimal

from app.services.price_comparator import ComparedOffer, PriceComparisonResult

PRICE_DISCLAIMER = (
    "Важно: цены взяты с сайтов магазинов и могут отличаться на кассе. "
    "Цены по картам и акции отмечены отдельно."
)


def money(value: Decimal | None) -> str:
    if value is None:
        return "нет цены"
    return f"{value.quantize(Decimal('0.01'))} ₽"


def compact_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _count_suffix(count: Decimal) -> str:
    if count == Decimal("1"):
        return ""
    return f" × {compact_decimal(count)}"


def _offer_line(offer: ComparedOffer, *, count: Decimal = Decimal("1")) -> str:
    store = offer.offer.store_product.store.display_name
    stale = ", данные могут быть устаревшими" if offer.is_stale else ""
    unit = ""
    if offer.effective_unit_price is not None and offer.effective_unit_price_unit:
        unit = f", {money(offer.effective_unit_price)} {offer.effective_unit_price_unit}"
    subtotal = ""
    if count != Decimal("1"):
        subtotal = f", за {compact_decimal(count)} шт: {money(offer.effective_price * count)}"
    confidence = min(100, max(0, offer.match.score))
    match = f", совпадение {confidence}%/{offer.match.match_type}"
    trend = ""
    if offer.price_trend_label != "истории мало":
        trend = f", {offer.price_trend_label}"
        if offer.price_delta_percent is not None:
            trend += f" ({compact_decimal(offer.price_delta_percent)}%)"
    return (
        f"{store} — {money(offer.effective_price)} "
        f"({offer.price_label}{unit}{subtotal}{match}{trend}{stale})"
    )


def _summary_lines(result: PriceComparisonResult) -> list[str]:
    lines: list[str] = []
    best_single = next(
        (store for store in result.one_store_basket if store.missing_items_count == 0),
        None,
    )
    if best_single is not None:
        lines.append(
            "Лучший один магазин: "
            f"{best_single.store.display_name} — {money(best_single.total_price)}."
        )
    if result.split_basket.picks:
        split_line = (
            f"Самый дешевый раздельный вариант: {money(result.split_basket.total_price)} "
            f"в {result.split_basket.number_of_stores} магазин(ах)."
        )
        if result.split_basket.estimated_savings_vs_best_single_store is not None:
            split_line += (
                " Экономия против лучшего одного магазина: "
                f"{money(result.split_basket.estimated_savings_vs_best_single_store)}."
            )
        lines.append(split_line)
    if result.stale_stores:
        lines.append(f"Устаревшие данные есть по магазинам: {', '.join(result.stale_stores)}.")
    if result.unavailable_stores:
        lines.append(f"Нет данных по магазинам: {', '.join(result.unavailable_stores)}.")
    return lines


def format_price_comparison(result: PriceComparisonResult) -> str:
    lines = ["Сравнение корзины", ""]
    summary = _summary_lines(result)
    if summary:
        lines.extend(summary)
        lines.append("")

    for index, per_item in enumerate(result.per_item_best, start=1):
        count_suffix = _count_suffix(per_item.item.purchase_count)
        lines.append(f"{index}. {per_item.item.raw_text}{count_suffix}")
        if not per_item.offers:
            lines.append(
                f"Не нашел цену для: {per_item.item.raw_text}. "
                "Попробуй указать бренд, объем или более точное название."
            )
            lines.append("")
            continue
        best = per_item.offers[0]
        lines.append(f"Лучше: {_offer_line(best, count=per_item.item.purchase_count)}")
        others = per_item.offers[1:4]
        if others:
            lines.append("Другие:")
            lines.extend(
                f"- {_offer_line(offer, count=per_item.item.purchase_count)}"
                for offer in others
            )
        if best.match.match_type == "similar":
            lines.append(
                "Комментарий: точное совпадение не найдено, показаны похожие товары."
            )
        lines.append("")

    if result.one_store_basket:
        lines.append("Если покупать все в одном магазине:")
        for index, total in enumerate(result.one_store_basket[:5], start=1):
            notes = []
            if total.card_items_count:
                notes.append(f"{total.card_items_count} товара по карте")
            if total.promo_items_count:
                notes.append(f"{total.promo_items_count} товара по акции")
            notes.extend(total.notes[:2])
            suffix = f", {', '.join(notes)}" if notes else ""
            total_items = total.found_items_count + total.missing_items_count
            found = f"{total.found_items_count}/{total_items}"
            lines.append(
                f"{index}. {total.store.display_name} — "
                f"{money(total.total_price)}, найдено {found}{suffix}"
            )
        lines.append("")

    lines.append("Самый дешевый вариант по разным магазинам:")
    lines.append(f"Итого: {money(result.split_basket.total_price)}")
    lines.append(f"Магазинов: {result.split_basket.number_of_stores}")
    if result.split_basket.estimated_savings_vs_best_single_store is not None:
        lines.append(
            "Экономия против лучшего одного магазина: "
            f"{money(result.split_basket.estimated_savings_vs_best_single_store)}"
        )
    lines.append("")
    lines.append(PRICE_DISCLAIMER)
    return "\n".join(lines)
