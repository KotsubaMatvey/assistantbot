from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import STORE_LABELS, settings_keyboard
from app.db.models import ComparisonMode
from app.db.repositories.users import get_or_create_user, get_settings_for_user
from app.db.session import SessionLocal

router = Router()


@router.message(Command("settings"))
async def settings_handler(message: Message) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user)
        await session.commit()
        user_settings = user.settings
    await message.answer(
        _settings_text(user_settings),
        reply_markup=settings_keyboard(user_settings.enabled_store_slugs),
    )


@router.callback_query(F.data.startswith("store:"))
async def toggle_store(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        return
    slug = callback.data.split(":", 1)[1]
    async with SessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user)
        user_settings = await get_settings_for_user(session, user.id)
        enabled = set(user_settings.enabled_store_slugs)
        if slug in enabled:
            enabled.remove(slug)
        else:
            enabled.add(slug)
        user_settings.enabled_store_slugs = list(enabled)
        await session.commit()
    await callback.message.edit_reply_markup(reply_markup=settings_keyboard(list(enabled)))
    await callback.answer()


@router.callback_query(F.data.startswith("card:"))
async def toggle_card(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        return
    slug = callback.data.split(":", 1)[1]
    attr = f"has_{slug}_card"
    async with SessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user)
        user_settings = await get_settings_for_user(session, user.id)
        setattr(user_settings, attr, not bool(getattr(user_settings, attr)))
        await session.commit()
    await callback.answer("Сохранено")


@router.callback_query(F.data.startswith("mode:"))
async def set_mode(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        return
    mode = callback.data.split(":", 1)[1]
    async with SessionLocal() as session:
        user = await get_or_create_user(session, callback.from_user)
        user_settings = await get_settings_for_user(session, user.id)
        user_settings.comparison_mode = ComparisonMode(mode)
        await session.commit()
    await callback.answer("Режим сохранён")


def _settings_text(settings: object) -> str:
    enabled = getattr(settings, "enabled_store_slugs", [])
    stores = ", ".join(STORE_LABELS[slug] for slug in enabled if slug in STORE_LABELS)
    return (
        f"Магазины: {stores or 'не выбраны'}\n"
        f"Режим сравнения: {getattr(settings, 'comparison_mode', 'mixed')}"
    )

