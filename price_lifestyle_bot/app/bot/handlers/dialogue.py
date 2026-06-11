from __future__ import annotations

from io import BytesIO

import httpx
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import get_settings
from app.services.chat_dialogue import (
    ChatDialogueEngine,
    ChatReply,
    daily_actions_keyboard,
)
from app.services.chat_history import ChatHistoryStore
from app.services.llm_client import answer_freeform_with_llm
from app.services.media_understanding import MediaUnderstandingClient

router = Router()

FREEFORM_UNAVAILABLE_TEXT = (
    "Я не сохранил это сообщение в память. Свободный диалог сейчас недоступен: "
    "LLM не подключён или временно не ответил.\n\n"
    "Для записи начни сообщение с «запомни ...», для задачи — «добавь задачу ...», "
    "для напоминания — «напомни ...»."
)


async def _answer_freeform(message: Message, text: str) -> None:
    settings = get_settings()
    history_store = ChatHistoryStore(settings.obsidian_vault_path)
    user_id = message.from_user.id if message.from_user else None
    history = (
        [
            {"role": turn.role, "content": turn.text}
            for turn in history_store.list_turns(user_id=user_id)
        ]
        if user_id is not None
        else []
    )
    llm_answer = await answer_freeform_with_llm(text=text, settings=settings, history=history)
    if llm_answer and user_id is not None:
        history_store.append_exchange(
            user_id=user_id,
            user_text=text,
            assistant_text=llm_answer,
        )
    await message.answer((llm_answer or FREEFORM_UNAVAILABLE_TEXT)[:3900])


def _engine() -> ChatDialogueEngine:
    settings = get_settings()
    return ChatDialogueEngine(settings.obsidian_vault_path, timezone_name=settings.timezone)


def _markup(reply: ChatReply) -> InlineKeyboardMarkup | None:
    if not reply.rows:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button.text, callback_data=button.data) for button in row]
            for row in reply.rows
        ]
    )


def _daily_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button.text, callback_data=button.data) for button in row]
            for row in daily_actions_keyboard()
        ]
    )


async def _send_reply(message: Message, reply: ChatReply) -> None:
    if reply.event == "freeform":
        await _answer_freeform(message, reply.text)
        return
    if reply.event == "morning":
        from app.bot.handlers.lifestyle import _morning_report

        await message.answer(await _morning_report(message), reply_markup=_daily_markup())
        return
    if reply.event == "evening":
        from app.bot.handlers.lifestyle import _evening_report

        await message.answer(_evening_report(message), reply_markup=_daily_markup())
        return
    if reply.event == "agenda":
        from app.services.agenda import build_agenda
        from app.services.assistant_jobs import AssistantJobStore
        from app.services.obsidian_memory import ObsidianMemory

        if message.from_user is None:
            return
        settings = get_settings()
        await message.answer(
            build_agenda(
                memory=ObsidianMemory(settings.obsidian_vault_path),
                jobs=AssistantJobStore(
                    settings.obsidian_vault_path,
                    timezone_name=settings.timezone,
                ),
                user_id=message.from_user.id,
                timezone_name=settings.timezone,
            ),
            reply_markup=_daily_markup(),
        )
        return
    if reply.text:
        await message.answer(reply.text[:3900], reply_markup=_markup(reply))


@router.callback_query(F.data.startswith("chat:brief:"))
async def daily_callback_handler(callback: CallbackQuery) -> None:
    if not isinstance(callback.message, Message) or callback.from_user is None:
        return
    event = (callback.data or "").removeprefix("chat:brief:")
    if event == "budget":
        from app.services.spending import SpendingStore, format_budget_summary

        settings = get_settings()
        text = format_budget_summary(
            SpendingStore(settings.obsidian_vault_path).budget_summary(
                user_id=callback.from_user.id,
            )
        )
        await callback.message.answer(text, reply_markup=_daily_markup())
    else:
        await _send_reply(callback.message, ChatReply("", event=event))
    await callback.answer()


@router.callback_query(F.data.startswith("chat:"))
async def dialogue_callback_handler(callback: CallbackQuery) -> None:
    if (
        not isinstance(callback.message, Message)
        or callback.from_user is None
        or callback.data is None
    ):
        return
    reply = _engine().handle_callback(user_id=callback.from_user.id, data=callback.data)
    await callback.message.answer(reply.text[:3900], reply_markup=_markup(reply))
    await callback.answer()


@router.message(F.voice)
async def dialogue_voice_handler(message: Message, bot: Bot) -> None:
    if message.from_user is None:
        return
    caption = (message.caption or "").strip()
    if caption:
        await _send_reply(
            message,
            _engine().handle_text(user_id=message.from_user.id, text=caption),
        )
        return
    settings = get_settings()
    media = MediaUnderstandingClient(settings)
    if not media.configured or message.voice is None:
        await _send_reply(message, _engine().expect_voice_transcript(user_id=message.from_user.id))
        return
    try:
        content = BytesIO()
        await bot.download(message.voice, destination=content)
        result = await media.transcribe_voice(content=content.getvalue())
    except (ValueError, httpx.HTTPError, OSError) as exc:
        await message.answer(f"Не удалось расшифровать голосовое: {exc}")
        return
    if result is None:
        await _send_reply(message, _engine().expect_voice_transcript(user_id=message.from_user.id))
        return
    await _send_reply(
        message,
        _engine().confirm_media_text(
            user_id=message.from_user.id,
            text=result.text,
            source="voice",
        ),
    )


@router.message(F.photo)
async def dialogue_photo_handler(message: Message, bot: Bot) -> None:
    if message.from_user is None:
        return
    caption = (message.caption or "").strip()
    if caption:
        await _send_reply(
            message,
            _engine().handle_photo_caption(user_id=message.from_user.id, caption=caption),
        )
        return
    settings = get_settings()
    media = MediaUnderstandingClient(settings)
    if not media.configured or not settings.media_vision_model.strip() or not message.photo:
        await _send_reply(message, _engine().expect_photo_receipt(user_id=message.from_user.id))
        return
    try:
        content = BytesIO()
        await bot.download(message.photo[-1], destination=content)
        result = await media.extract_receipt(content=content.getvalue())
    except (ValueError, httpx.HTTPError, OSError) as exc:
        await message.answer(f"Не удалось распознать чек: {exc}")
        return
    if result is None:
        await _send_reply(message, _engine().expect_photo_receipt(user_id=message.from_user.id))
        return
    await _send_reply(
        message,
        _engine().confirm_media_text(
            user_id=message.from_user.id,
            text=result.text,
            source="receipt",
        ),
    )


@router.message(F.text, ~F.text.startswith("/"))
async def dialogue_text_handler(message: Message) -> None:
    if message.from_user is None:
        return
    await _send_reply(
        message,
        _engine().handle_text(user_id=message.from_user.id, text=message.text or ""),
    )
