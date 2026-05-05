from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from app.db.repositories.sessions import append_bot_message, get_or_create_bot_session
from app.db.repositories.users import get_or_create_user
from app.db.session import SessionLocal
from app.logging_config import get_logger

logger = get_logger(__name__)


class ErrorLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:
            user = data.get("event_from_user")
            logger.exception(
                "handler_failed",
                user_id=getattr(user, "id", None),
                error=str(exc),
            )
            raise


class InteractionLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        await self._log_event(event, data)
        return await handler(event, data)

    async def _log_event(self, event: TelegramObject, data: dict[str, Any]) -> None:
        extracted = _extract_event(event)
        if extracted is None:
            return
        chat_id, message_type, text, raw_payload = extracted
        telegram_user = data.get("event_from_user")
        if telegram_user is None:
            return
        command = _extract_command(text)
        try:
            async with SessionLocal() as session:
                user = await get_or_create_user(session, telegram_user)
                bot_session = await get_or_create_bot_session(
                    session,
                    user=user,
                    platform="telegram",
                    chat_id=chat_id,
                )
                await append_bot_message(
                    session,
                    bot_session=bot_session,
                    direction="in",
                    message_type=message_type,
                    text=text,
                    command=command,
                    raw_payload=raw_payload,
                )
                await session.commit()
        except Exception as exc:
            logger.warning("interaction_log_failed", error=str(exc))


def _extract_event(
    event: TelegramObject,
) -> tuple[int | str, str, str | None, dict[str, object]] | None:
    if isinstance(event, Update):
        if event.message is not None:
            return _extract_message(event.message)
        if event.callback_query is not None:
            return _extract_callback(event.callback_query)
        return None
    if isinstance(event, Message):
        return _extract_message(event)
    if isinstance(event, CallbackQuery):
        return _extract_callback(event)
    return None


def _extract_message(message: Message) -> tuple[int | str, str, str | None, dict[str, object]]:
    return (
        message.chat.id,
        "message",
        message.text or message.caption,
        {
            "message_id": message.message_id,
            "chat_type": message.chat.type,
        },
    )


def _extract_callback(
    callback: CallbackQuery,
) -> tuple[int | str, str, str | None, dict[str, object]] | None:
    if callback.message is None:
        return None
    return (
        callback.message.chat.id,
        "callback",
        callback.data,
        {
            "message_id": callback.message.message_id,
            "callback_id": callback.id,
        },
    )


def _extract_command(text: str | None) -> str | None:
    if not text or not text.startswith("/"):
        return None
    command = text.split(maxsplit=1)[0].lstrip("/")
    return command.split("@", 1)[0] or None
