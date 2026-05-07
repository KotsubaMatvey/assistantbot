from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantPersona:
    name: str
    title: str
    description: str
    commands: list[str]
    pixel_mood: str


PERSONAS: tuple[AssistantPersona, ...] = (
    AssistantPersona(
        name="secretary",
        title="Secretary",
        description="задачи, agenda, напоминания, compact и порядок в памяти",
        commands=["agenda", "status", "compact", "new"],
        pixel_mood="calm",
    ),
    AssistantPersona(
        name="buyer",
        title="Buyer",
        description="корзины, price alerts, pantry, чеки и бюджет",
        commands=["prices", "watch_price", "pantry", "budget"],
        pixel_mood="focused",
    ),
    AssistantPersona(
        name="market_analyst",
        title="Market Analyst",
        description="BTC, BTC.D, индексы и утренние market briefs",
        commands=["markets", "morning", "automation_enable"],
        pixel_mood="sharp",
    ),
)


def list_personas() -> list[AssistantPersona]:
    return list(PERSONAS)


def get_persona(name: str) -> AssistantPersona | None:
    normalized = name.strip().lower().replace("-", "_")
    return next((persona for persona in PERSONAS if persona.name == normalized), None)


def format_personas(active: str | None = None) -> str:
    lines = ["Assistants:"]
    for persona in PERSONAS:
        marker = "*" if persona.name == active else "-"
        lines.append(f"{marker} {persona.name}: {persona.description}")
        lines.append(f"  commands: {', '.join('/' + item for item in persona.commands)}")
    return "\n".join(lines)
