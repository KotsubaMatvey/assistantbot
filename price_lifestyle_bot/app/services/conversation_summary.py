from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationSummary:
    title: str
    body: str


def summarize_conversation(messages: list[str], *, limit: int = 12) -> ConversationSummary:
    clean_messages = [message.strip() for message in messages if message and message.strip()]
    if not clean_messages:
        return ConversationSummary(title="Conversation summary", body="No messages to summarize.")
    recent = clean_messages[-limit:]
    tasks = [message for message in recent if _looks_like_task(message)]
    decisions = [message for message in recent if _looks_like_decision(message)]
    lines = ["# Conversation summary", "", "## Recent messages"]
    lines.extend(f"- {message[:240]}" for message in recent)
    if tasks:
        lines.extend(["", "## Possible tasks"])
        lines.extend(f"- {message[:240]}" for message in tasks)
    if decisions:
        lines.extend(["", "## Possible decisions"])
        lines.extend(f"- {message[:240]}" for message in decisions)
    return ConversationSummary(title="Conversation summary", body="\n".join(lines))


def _looks_like_task(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ("todo", "надо", "нужно", "сделать", "задача"))


def _looks_like_decision(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ("решили", "выбрать", "decision", "вариант"))
