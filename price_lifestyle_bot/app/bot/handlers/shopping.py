from __future__ import annotations

from dataclasses import replace

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.message_utils import answer_long
from app.config import get_settings
from app.services.basket_parser import parse_basket
from app.services.formatting import format_price_comparison
from app.services.obsidian_memory import ObsidianMemory, PriceMemoryContext
from app.services.price_comparator import compare_prices, offer_from_snapshot_with_history

router = Router()


@router.message(Command("prices"))
async def prices_command(message: Message) -> None:
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer(
            "Пришли список товаров после /prices или обычным сообщением."
        )
        return
    await _handle_basket(message, text)


@router.message(Command("last"))
async def last_basket_command(message: Message) -> None:
    if message.from_user is None:
        return
    from app.db.repositories.baskets import get_latest_basket_for_user
    from app.db.repositories.users import get_or_create_user
    from app.db.session import SessionLocal

    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user)
        basket = await get_latest_basket_for_user(session, user.id)
        await session.commit()
    if basket is None:
        await message.answer("Последней корзины пока нет. Пришли список покупок обычным текстом.")
        return
    await _handle_basket(message, basket.raw_text)


async def _handle_basket(message: Message, text: str) -> None:
    if message.from_user is None:
        return
    items = parse_basket(text)
    if not items:
        await message.answer(
            "Не понял список. Пришли товары строками или через запятую."
        )
        return

    settings = get_settings()
    memory = ObsidianMemory(settings.obsidian_vault_path)
    memory_context = PriceMemoryContext()
    from app.db.repositories.baskets import create_basket
    from app.db.repositories.users import get_or_create_user, get_settings_for_user
    from app.db.session import SessionLocal

    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user)
        user_settings = await get_settings_for_user(session, user.id)
        await create_basket(session, user_id=user.id, raw_text=text, items=items)
        memory.remember_basket(user_id=message.from_user.id, raw_text=text, items=items)
        memory_context = memory.build_price_context(user_id=message.from_user.id, items=items)
        effective_settings = memory.settings_with_memory(user_settings, memory_context)
        store_slugs = _selected_store_slugs(effective_settings)
        await session.commit()

    if settings.live_price_refresh_enabled:
        from app.services.live_price_refresh import refresh_prices_for_items

        await message.answer("Обновляю текущие цены по выбранным магазинам.")
        refresh_result = await refresh_prices_for_items(
            items,
            store_slugs,
            limit_per_query=settings.live_price_refresh_limit_per_query,
        )
        if refresh_result.failed_store_slugs:
            await message.answer(
                "Не удалось обновить текущие цены: "
                f"{', '.join(refresh_result.failed_store_slugs)}. "
                "Использую последние сохраненные данные."
            )

    from app.db.repositories.prices import (
        get_latest_prices_by_store_products,
        get_price_history_stats,
    )

    async with SessionLocal() as session:
        snapshots = await get_latest_prices_by_store_products(session)
        history = await get_price_history_stats(
            session,
            store_product_ids=[snapshot.store_product_id for snapshot in snapshots],
        )

    offers = [
        offer_from_snapshot_with_history(snapshot, history.get(snapshot.store_product_id))
        for snapshot in snapshots
    ]
    result = compare_prices(
        items,
        effective_settings,
        offers,
        freshness_hours=settings.price_freshness_hours,
    )
    enabled = set(effective_settings.enabled_store_slugs)
    stores_with_prices = {offer.store_product.store.slug for offer in offers}
    unavailable = sorted(enabled - stores_with_prices)
    stale_stores = sorted(
        {
            offer.offer.store_product.store.slug
            for per_item in result.per_item_best
            for offer in per_item.offers
            if offer.is_stale
        }
    )
    result = replace(result, unavailable_stores=unavailable, stale_stores=stale_stores)
    heads_up = memory.format_price_heads_up(
        context=memory_context,
        original_settings=user_settings,
    )
    comparison = format_price_comparison(result)
    if heads_up:
        comparison = f"{heads_up}\n\n{comparison}"
    await answer_long(message, comparison, disable_web_page_preview=True)


def _selected_store_slugs(user_settings: object) -> list[str]:
    enabled = list(getattr(user_settings, "enabled_store_slugs", []) or [])
    from app.scrapers.registry import list_scrapers

    return enabled or list_scrapers()
