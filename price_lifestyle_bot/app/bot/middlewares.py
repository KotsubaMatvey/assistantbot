from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from app.config import get_settings
from app.db.repositories.sessions import append_bot_message, get_or_create_bot_session
from app.db.repositories.users import get_or_create_user
from app.db.session import SessionLocal
from app.logging_config import get_logger
from app.services.access_control import AccessControlStore
from app.services.assistant_runtime import AssistantRuntimeStore

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
        settings = get_settings()
        runtime = AssistantRuntimeStore(settings.obsidian_vault_path)
        session_epoch = runtime.get_state(user_id=telegram_user.id).session_epoch
        try:
            async with SessionLocal() as session:
                user = await get_or_create_user(session, telegram_user)
                bot_session = await get_or_create_bot_session(
                    session,
                    user=user,
                    platform="telegram",
                    chat_id=chat_id,
                    session_epoch=session_epoch,
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


class AccessControlMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        settings = get_settings()
        message = _message_from_event(event)
        if message is not None and not should_process_group_message(
            chat_type=message.chat.type,
            text=message.text or message.caption,
            policy=settings.assistant_group_trigger_policy,
            bot_username=_bot_username(data),
            is_reply_to_bot=_is_reply_to_bot(message),
        ):
            return None
        mode = settings.assistant_access_mode
        if mode == "open":
            return await handler(event, data)
        telegram_user = data.get("event_from_user")
        user_id = getattr(telegram_user, "id", None)
        if user_id is None:
            return await handler(event, data)
        access = AccessControlStore(settings.obsidian_vault_path)
        if access.is_allowed(
            user_id=user_id,
            mode=mode,
            admin_ids=settings.admin_telegram_ids,
        ):
            return await handler(event, data)
        if message is not None:
            pairing = access.create_pairing_code(
                user_id=user_id,
                ttl_minutes=settings.assistant_pairing_ttl_minutes,
            )
            await message.answer(
                "Доступ к ассистенту закрыт. Отправь администратору код "
                f"{pairing.code} для подтверждения."
            )
        return None


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


def _message_from_event(event: TelegramObject) -> Message | None:
    if isinstance(event, Update):
        return event.message
    if isinstance(event, Message):
        return event
    return None


def should_process_group_message(
    *,
    chat_type: str,
    text: str | None,
    policy: str,
    bot_username: str | None,
    is_reply_to_bot: bool,
) -> bool:
    if chat_type == "private":
        return True
    normalized_policy = policy.strip().lower()
    if normalized_policy == "always":
        return True
    if normalized_policy != "mention":
        return False
    clean_text = text or ""
    if clean_text.startswith("/"):
        return True
    if is_reply_to_bot:
        return True
    if bot_username and f"@{bot_username.lower()}" in clean_text.lower():
        return True
    return False


def _bot_username(data: dict[str, Any]) -> str | None:
    bot = data.get("bot")
    username = getattr(bot, "username", None)
    if isinstance(username, str):
        return username
    bot_info = getattr(bot, "me", None)
    info_username = getattr(bot_info, "username", None)
    return info_username if isinstance(info_username, str) else None


def _is_reply_to_bot(message: Message) -> bool:
    replied = message.reply_to_message
    if replied is None or replied.from_user is None:
        return False
    return bool(replied.from_user.is_bot)
