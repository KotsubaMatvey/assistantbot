from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.commands import help_text
from app.bot.message_utils import answer_long

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    if message.from_user is None:
        return
    from app.db.repositories.users import get_or_create_user
    from app.db.session import SessionLocal

    async with SessionLocal() as session:
        await get_or_create_user(session, message.from_user)
        await session.commit()
    await message.answer(
        "Привет. Я твой second brain assistant.\n\n"
        "Пиши мне обычным текстом. Для действий используй явные фразы: "
        "«напомни завтра в 9 позвонить врачу», «потратил 740 на продукты», "
        "«добавь молоко в покупки», «запомни, что мама предпочитает чай». "
        "Остальные сообщения идут в диалог и сами по себе не сохраняются в память. "
        "После записи можно отменить или изменить действие кнопкой; "
        "история доступна фразой «покажи историю изменений». "
        "Напиши «что ты умеешь», чтобы увидеть примеры.\n\n"
        "Быстрый старт:\n"
        "/agenda — что важно сейчас\n"
        "/today — лента сегодняшней памяти\n"
        "/tasks — открытые задачи\n"
        "/status — состояние ассистента\n"
        "/new — новая логическая сессия\n"
        "/compact — сжать текущий контекст\n"
        "/help — все команды\n\n"
        "Mini App открывается кнопкой над полем ввода.",
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await answer_long(message, help_text())
