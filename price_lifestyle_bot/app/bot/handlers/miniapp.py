from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from app.bot.handlers.markets import markets_command
from app.bot.handlers.memory import (
    agenda_handler,
    compact_handler,
    new_session_handler,
    status_handler,
)
from app.bot.handlers.shopping import _handle_basket
from app.services.mini_app import parse_mini_app_payload

router = Router()


@router.message(F.web_app_data)
async def mini_app_data_handler(message: Message) -> None:
    raw_data = message.web_app_data.data if message.web_app_data else ""
    try:
        payload = parse_mini_app_payload(raw_data)
    except ValueError as exc:
        await message.answer(f"Mini App payload не обработан: {exc}")
        return

    if payload.type == "basket_compare":
        await _handle_basket(message, payload.text)
        return

    if payload.command == "markets":
        await markets_command(message)
    elif payload.command == "status":
        await status_handler(message)
    elif payload.command == "agenda":
        await agenda_handler(message)
    elif payload.command == "compact":
        await compact_handler(message)
    elif payload.command == "new":
        await new_session_handler(message)
