from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.bot.handlers import dialogue
from app.services.chat_dialogue import ChatReply
from app.services.chat_history import ChatHistoryStore


class FakeMessage:
    def __init__(self, user_id: int | None = 101) -> None:
        self.answers: list[str] = []
        self.from_user = SimpleNamespace(id=user_id) if user_id is not None else None

    async def answer(self, text: str, reply_markup: object | None = None) -> None:
        self.answers.append(text)


def _settings(tmp_path) -> SimpleNamespace:
    return SimpleNamespace(obsidian_vault_path=str(tmp_path))


@pytest.mark.asyncio
async def test_freeform_chat_reply_uses_existing_llm_path(monkeypatch, tmp_path) -> None:
    message = FakeMessage()
    seen: list[str] = []

    async def answer_freeform_with_llm(*, text: str, settings: object, history=None) -> str:
        seen.append(text)
        return "Ответ ассистента"

    monkeypatch.setattr(dialogue, "get_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(dialogue, "answer_freeform_with_llm", answer_freeform_with_llm)

    await dialogue._send_reply(message, ChatReply("Привет", event="freeform"))  # type: ignore[arg-type]

    assert seen == ["Привет"]
    assert message.answers == ["Ответ ассистента"]


@pytest.mark.asyncio
async def test_freeform_chat_reply_does_not_claim_memory_capture_without_llm(
    monkeypatch, tmp_path
) -> None:
    message = FakeMessage()

    async def answer_freeform_with_llm(*, text: str, settings: object, history=None) -> None:
        return None

    monkeypatch.setattr(dialogue, "get_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(dialogue, "answer_freeform_with_llm", answer_freeform_with_llm)

    await dialogue._send_reply(message, ChatReply("Привет", event="freeform"))  # type: ignore[arg-type]

    assert "не сохранил" in message.answers[0]
    assert "запомни" in message.answers[0]


@pytest.mark.asyncio
async def test_freeform_chat_keeps_rolling_history_between_messages(
    monkeypatch, tmp_path
) -> None:
    message = FakeMessage(user_id=77)
    received_histories: list[list[dict[str, str]]] = []

    async def answer_freeform_with_llm(*, text: str, settings: object, history=None) -> str:
        received_histories.append(list(history or []))
        return f"Ответ на: {text}"

    monkeypatch.setattr(dialogue, "get_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(dialogue, "answer_freeform_with_llm", answer_freeform_with_llm)

    await dialogue._send_reply(message, ChatReply("Первое", event="freeform"))  # type: ignore[arg-type]
    await dialogue._send_reply(message, ChatReply("Второе", event="freeform"))  # type: ignore[arg-type]

    assert received_histories[0] == []
    assert received_histories[1] == [
        {"role": "user", "content": "Первое"},
        {"role": "assistant", "content": "Ответ на: Первое"},
    ]
    turns = ChatHistoryStore(str(tmp_path)).list_turns(user_id=77)
    assert [turn.text for turn in turns] == [
        "Первое",
        "Ответ на: Первое",
        "Второе",
        "Ответ на: Второе",
    ]


@pytest.mark.asyncio
async def test_failed_llm_answer_is_not_recorded_in_history(monkeypatch, tmp_path) -> None:
    message = FakeMessage(user_id=78)

    async def answer_freeform_with_llm(*, text: str, settings: object, history=None) -> None:
        return None

    monkeypatch.setattr(dialogue, "get_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(dialogue, "answer_freeform_with_llm", answer_freeform_with_llm)

    await dialogue._send_reply(message, ChatReply("Привет", event="freeform"))  # type: ignore[arg-type]

    assert ChatHistoryStore(str(tmp_path)).list_turns(user_id=78) == []
