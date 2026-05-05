from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.commands import help_text
from app.bot.keyboards import settings_keyboard
from app.db.repositories.users import get_or_create_user
from app.db.session import SessionLocal

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user)
        await session.commit()
        enabled = user.settings.enabled_store_slugs
    await message.answer(
        "Привет. Пришли список товаров, каждый товар с новой строки.\n\n"
        "Пример:\n"
        "молоко 2.5 1 л\n"
        "яйца C1 10 шт\n"
        "сахар 1 кг\n\n"
        "В настройках можно выбрать магазины, карты лояльности и режим сравнения.",
        reply_markup=settings_keyboard(enabled),
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(help_text())
