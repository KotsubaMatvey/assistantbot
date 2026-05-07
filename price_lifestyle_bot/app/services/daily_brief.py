from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DailyBrief:
    agenda: str
    markets: str
    price_alerts: str
    pantry: str
    budget: str
    notes: list[str] = field(default_factory=list)


def format_daily_brief(brief: DailyBrief) -> str:
    sections = [
        ("План", brief.agenda),
        ("Рынки", _without_title(brief.markets, "Рынки")),
        ("Ценовые сигналы", brief.price_alerts),
        ("Дом", brief.pantry),
        ("Бюджет", brief.budget),
    ]
    lines = ["Утренний дайджест", ""]
    for title, body in sections:
        clean = body.strip()
        if not clean:
            continue
        lines.extend([f"## {title}", clean[:900], ""])
    if brief.notes:
        lines.append("## Фокус")
        lines.extend(f"- {note}" for note in brief.notes[:5])
    return "\n".join(lines).strip()


def _without_title(text: str, title: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip().lower() == title.lower():
        return "\n".join(lines[1:]).strip()
    return text
