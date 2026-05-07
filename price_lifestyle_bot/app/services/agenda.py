from __future__ import annotations

from zoneinfo import ZoneInfo

from app.services.assistant_jobs import AssistantJobStore
from app.services.obsidian_memory import ObsidianMemory


def build_agenda(
    *,
    memory: ObsidianMemory,
    jobs: AssistantJobStore,
    user_id: int,
    timezone_name: str,
) -> str:
    timezone = ZoneInfo(timezone_name)
    reminders = memory.list_reminders(user_id=user_id, limit=5)
    tasks = memory.list_open_tasks(user_id=user_id, limit=5)
    pins = memory.list_pins(user_id=user_id, limit=3)
    user_jobs = jobs.list_jobs(user_id=user_id)[:5]
    lines = ["Agenda"]
    if reminders:
        lines.append("")
        lines.append("Reminders:")
        for reminder in reminders:
            due_at = reminder.due_at.astimezone(timezone)
            lines.append(f"- {due_at:%Y-%m-%d %H:%M}: {reminder.snippet}")
    if tasks:
        lines.append("")
        lines.append("Open tasks:")
        lines.extend(f"- {task.snippet} ({task.id})" for task in tasks)
    if user_jobs:
        lines.append("")
        lines.append("Jobs:")
        for job in user_jobs:
            next_at = job.next_run_at.astimezone(timezone)
            lines.append(f"- {next_at:%Y-%m-%d %H:%M}: {job.message} ({job.id})")
    if pins:
        lines.append("")
        lines.append("Important:")
        lines.extend(f"- {pin.snippet}" for pin in pins)
    if len(lines) == 1:
        lines.append("No reminders, jobs, tasks, or pins.")
    return "\n".join(lines)[:3900]
