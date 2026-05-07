from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings
from app.services.market_watch import (
    fetch_market_watch,
    format_market_watch,
    market_watch_memory_note,
)
from app.services.obsidian_memory import ObsidianMemory

router = Router()


@router.message(Command("markets"))
async def markets_command(message: Message) -> None:
    result = await fetch_market_watch()
    if message.from_user is not None:
        ObsidianMemory(get_settings().obsidian_vault_path).remember_user_note(
            user_id=message.from_user.id,
            text=market_watch_memory_note(result),
            note_type="market",
            extra_tags=["market", "prices"],
        )
    await message.answer(format_market_watch(result))
