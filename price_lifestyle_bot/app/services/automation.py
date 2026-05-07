from __future__ import annotations

from dataclasses import dataclass

from app.services.assistant_jobs import AssistantJob, AssistantJobStore


@dataclass(frozen=True)
class AutomationTemplate:
    name: str
    description: str
    schedule_type: str
    schedule_value: str
    delivery_mode: str
    message: str


AUTOMATION_TEMPLATES: tuple[AutomationTemplate, ...] = (
    AutomationTemplate(
        name="morning_digest",
        description="ежедневно присылать agenda, рынки, pantry, бюджет и price alerts",
        schedule_type="daily",
        schedule_value="08:00",
        delivery_mode="morning",
        message="daily control brief",
    ),
    AutomationTemplate(
        name="market_watch",
        description="ежедневно присылать BTC, BTC.D и главные индексы",
        schedule_type="daily",
        schedule_value="08:05",
        delivery_mode="markets",
        message="morning market watch",
    ),
    AutomationTemplate(
        name="price_alerts",
        description="ежедневно проверять сохранённые ценовые сигналы",
        schedule_type="daily",
        schedule_value="08:10",
        delivery_mode="price_alerts",
        message="check watched grocery prices",
    ),
)


def list_automation_templates() -> list[AutomationTemplate]:
    return list(AUTOMATION_TEMPLATES)


def enable_automation(
    *,
    jobs: AssistantJobStore,
    user_id: int,
    name: str,
) -> AssistantJob:
    template = next((item for item in AUTOMATION_TEMPLATES if item.name == name), None)
    if template is None:
        raise ValueError("unknown automation template")
    return jobs.add_job(
        user_id=user_id,
        schedule_type=template.schedule_type,
        schedule_value=template.schedule_value,
        delivery_mode=template.delivery_mode,
        message=template.message,
    )


def format_automations(templates: list[AutomationTemplate]) -> str:
    lines = ["Automation templates:"]
    lines.extend(
        f"- {item.name}: {item.schedule_type} {item.schedule_value}, "
        f"{item.delivery_mode} — {item.description}"
        for item in templates
    )
    return "\n".join(lines)
