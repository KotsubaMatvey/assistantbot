from __future__ import annotations

from collections.abc import Iterable

from aiogram.types import Message


def split_telegram_text(text: str, *, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for line in text.splitlines():
        line_size = len(line) + 1
        if current and current_size + line_size > limit:
            chunks.append("\n".join(current))
            current = []
            current_size = 0
        if line_size > limit:
            chunks.extend(_split_long_line(line, limit=limit))
            continue
        current.append(line)
        current_size += line_size
    if current:
        chunks.append("\n".join(current))
    return chunks


async def answer_long(
    message: Message,
    text: str,
    *,
    disable_web_page_preview: bool = False,
) -> None:
    for chunk in split_telegram_text(text):
        await message.answer(chunk, disable_web_page_preview=disable_web_page_preview)


def _split_long_line(line: str, *, limit: int) -> Iterable[str]:
    return [line[index : index + limit] for index in range(0, len(line), limit)]
