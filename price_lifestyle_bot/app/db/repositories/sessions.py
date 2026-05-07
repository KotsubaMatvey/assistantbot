from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BotMessage, BotSession, User


def build_session_key(
    *,
    platform: str,
    chat_id: int | str,
    user_id: int,
    session_epoch: int = 0,
) -> str:
    suffix = f":epoch:{session_epoch}" if session_epoch > 0 else ""
    return f"{platform}:{chat_id}:user:{user_id}{suffix}"


async def get_or_create_bot_session(
    session: AsyncSession,
    *,
    user: User,
    platform: str,
    chat_id: int | str,
    session_epoch: int = 0,
) -> BotSession:
    session_key = build_session_key(
        platform=platform,
        chat_id=chat_id,
        user_id=user.id,
        session_epoch=session_epoch,
    )
    result = await session.execute(select(BotSession).where(BotSession.session_key == session_key))
    bot_session = result.scalar_one_or_none()
    if bot_session is None:
        bot_session = BotSession(
            user_id=user.id,
            platform=platform,
            chat_id=str(chat_id),
            session_key=session_key,
        )
        session.add(bot_session)
        await session.flush()
    return bot_session


async def append_bot_message(
    session: AsyncSession,
    *,
    bot_session: BotSession,
    direction: str,
    message_type: str,
    text: str | None,
    command: str | None = None,
    raw_payload: dict[str, object] | None = None,
) -> BotMessage:
    message = BotMessage(
        session_id=bot_session.id,
        direction=direction,
        message_type=message_type,
        text=text,
        command=command,
        raw_payload=raw_payload,
    )
    session.add(message)
    await session.flush()
    return message
