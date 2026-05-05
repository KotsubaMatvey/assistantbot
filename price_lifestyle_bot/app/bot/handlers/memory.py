from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings
from app.services.knowledge_ingestion import (
    add_rss_subscription,
    fetch_feed_digests,
    fetch_page_summary,
    format_digest_memory_note,
    format_feed_digests,
    format_learned_page_note,
    list_rss_subscriptions,
)
from app.services.obsidian_memory import ObsidianMemory

router = Router()


@router.message(Command("remember"))
async def remember_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /remember <что запомнить>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    path = memory.remember_user_note(user_id=message.from_user.id, text=text)
    await message.answer(f"Запомнил: {path.name}")


@router.message(Command("memory"))
async def memory_search_handler(message: Message) -> None:
    if message.from_user is None:
        return
    query = (message.text or "").partition(" ")[2].strip()
    if not query:
        await message.answer("Использование: /memory <что найти>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    results = memory.search_user_notes(user_id=message.from_user.id, query=query)
    if not results:
        await message.answer("В памяти ничего не нашел.")
        return

    lines = ["Нашел в памяти:"]
    for index, result in enumerate(results, start=1):
        tags = f" [{', '.join(result.tags)}]" if result.tags else ""
        lines.append(f"{index}. {result.snippet}{tags}")
    await message.answer("\n\n".join(lines))


@router.message(Command("ask"))
async def memory_ask_handler(message: Message) -> None:
    if message.from_user is None:
        return
    question = (message.text or "").partition(" ")[2].strip()
    if not question:
        await message.answer("Использование: /ask <вопрос к памяти>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    await message.answer(memory.ask_user_memory(user_id=message.from_user.id, question=question))


@router.message(Command("learn_url"))
async def learn_url_handler(message: Message) -> None:
    if message.from_user is None:
        return
    url = (message.text or "").partition(" ")[2].strip()
    if not url:
        await message.answer("Использование: /learn_url <ссылка>")
        return

    settings = get_settings()
    try:
        page = await fetch_page_summary(url)
    except Exception as exc:
        await message.answer(f"Не удалось прочитать ссылку: {str(exc)[:300]}")
        return

    memory = ObsidianMemory(settings.obsidian_vault_path)
    memory.remember_user_note(
        user_id=message.from_user.id,
        text=format_learned_page_note(page),
    )
    await message.answer(f"Сохранил в память: {page.title}")


@router.message(Command("rss_add"))
async def rss_add_handler(message: Message) -> None:
    if message.from_user is None:
        return
    feed_url = (message.text or "").partition(" ")[2].strip()
    if not feed_url:
        await message.answer("Использование: /rss_add <rss-or-atom-url>")
        return

    try:
        path = add_rss_subscription(
            get_settings().obsidian_vault_path,
            user_id=message.from_user.id,
            feed_url=feed_url,
        )
    except Exception as exc:
        await message.answer(f"Не удалось добавить RSS: {str(exc)[:300]}")
        return
    await message.answer(f"RSS добавлен: {path.name}")


@router.message(Command("rss_digest"))
async def rss_digest_handler(message: Message) -> None:
    if message.from_user is None:
        return
    settings = get_settings()
    subscriptions = list_rss_subscriptions(
        settings.obsidian_vault_path,
        user_id=message.from_user.id,
    )
    if not subscriptions:
        await message.answer("RSS-подписок пока нет. Добавь через /rss_add <url>.")
        return

    digests = await fetch_feed_digests(subscriptions, limit_per_feed=3)
    text = format_feed_digests(digests)
    memory = ObsidianMemory(settings.obsidian_vault_path)
    memory.remember_user_note(user_id=message.from_user.id, text=format_digest_memory_note(digests))
    await message.answer(text[:3900])
