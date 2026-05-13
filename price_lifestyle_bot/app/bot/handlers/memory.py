from __future__ import annotations

from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy import desc, select

from app.bot.feature_flags import is_feature_enabled
from app.config import get_settings
from app.db.models import BotMessage, BotSession
from app.db.repositories.users import get_or_create_user
from app.db.session import SessionLocal
from app.services.action_approvals import ActionApprovalStore
from app.services.agenda import build_agenda
from app.services.assistant_contract import assistant_capabilities
from app.services.assistant_jobs import AssistantJobStore, parse_job_request
from app.services.assistant_runtime import ASSISTANT_MODES, AssistantRuntimeStore, parse_on_off
from app.services.assistant_skills import AssistantSkillStore
from app.services.assistant_tools import list_tools, run_tool
from app.services.audit_log import AuditLogStore
from app.services.conversation_summary import summarize_conversation
from app.services.knowledge_ingestion import (
    add_rss_subscription,
    fetch_feed_digests,
    fetch_page_summary,
    format_digest_memory_note,
    format_feed_digests,
    format_learned_page_note,
    list_rss_subscriptions,
)
from app.services.memory_transfer import export_user_memory, import_user_memory
from app.services.mini_app import format_mini_app_status, mini_app_manifest
from app.services.obsidian_memory import (
    ObsidianMemory,
    parse_reminder_request,
    parse_space_prefix,
)
from app.services.source_trust import build_source_trust, format_source_trust
from app.services.standing_orders import StandingOrderStore

router = Router()


def _format_memory_result(index: int, snippet: str, citation: str, tags: list[str]) -> str:
    tags_text = f" [{', '.join(tags)}]" if tags else ""
    return f"{index}. {snippet}{tags_text}\nИсточник: {citation}"


def _audit(user_id: int, action: str, detail: str = "") -> None:
    AuditLogStore(get_settings().obsidian_vault_path).record(
        user_id=user_id,
        action=action,
        detail=detail,
    )


@router.message(Command("capture"))
async def capture_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /capture <мысль, задача, факт или ссылка>")
        return
    await _capture_text(message, text)


async def _capture_text(message: Message, text: str) -> None:
    if message.from_user is None:
        return
    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    active_space = memory.get_active_space(message.from_user.id)
    space, body = parse_space_prefix(text, default_space=active_space)
    related = memory.related_context(user_id=message.from_user.id, text=body, limit=3, space=space)
    path = memory.remember_user_note(user_id=message.from_user.id, text=body, space=space)
    lines = [f"Сохранил в second brain: {path.name}"]
    if related:
        lines.append("")
        lines.append("Связанный контекст:")
        lines.extend(f"- {result.snippet}\n  {result.citation}" for result in related)
    await message.answer("\n".join(lines))


@router.message(Command("today"))
async def today_handler(message: Message) -> None:
    if message.from_user is None:
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    await message.answer(memory.today_digest(user_id=message.from_user.id))


@router.message(Command("task"))
async def task_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /task <задача>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    active_space = memory.get_active_space(message.from_user.id)
    space, body = parse_space_prefix(text, default_space=active_space)
    path = memory.create_task(user_id=message.from_user.id, text=body, space=space)
    await message.answer(f"Задача сохранена. ID: {path.stem}")


@router.message(Command("preference"))
async def preference_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /preference <предпочтение>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    active_space = memory.get_active_space(message.from_user.id)
    space, body = parse_space_prefix(text, default_space=active_space)
    path = memory.remember_preference(user_id=message.from_user.id, text=body, space=space)
    await message.answer(f"Предпочтение сохранено: {path.name}")


@router.message(Command("lifestyle_context"))
async def lifestyle_context_handler(message: Message) -> None:
    if message.from_user is None:
        return
    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    await message.answer(memory.format_lifestyle_context(user_id=message.from_user.id))


@router.message(Command("journal"))
async def journal_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /journal <запись>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    active_space = memory.get_active_space(message.from_user.id)
    space, body = parse_space_prefix(text, default_space=active_space)
    path = memory.create_journal_entry(user_id=message.from_user.id, text=body, space=space)
    await message.answer(f"Запись журнала сохранена: {path.name}")


@router.message(Command("digest"))
async def digest_handler(message: Message) -> None:
    if message.from_user is None:
        return
    days_text = (message.text or "").partition(" ")[2].strip()
    days = 7
    if days_text:
        try:
            days = int(days_text)
        except ValueError:
            await message.answer("Использование: /digest [дней]")
            return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    await message.answer(memory.period_digest(user_id=message.from_user.id, days=days))


@router.message(Command("agenda"))
async def agenda_handler(message: Message) -> None:
    if message.from_user is None:
        return
    settings = get_settings()
    memory = ObsidianMemory(settings.obsidian_vault_path)
    jobs = AssistantJobStore(settings.obsidian_vault_path, timezone_name=settings.timezone)
    await message.answer(
        build_agenda(
            memory=memory,
            jobs=jobs,
            user_id=message.from_user.id,
            timezone_name=settings.timezone,
        )
    )


@router.message(Command("export_memory"))
async def export_memory_handler(message: Message) -> None:
    if message.from_user is None:
        return
    result = export_user_memory(
        vault_path=get_settings().obsidian_vault_path,
        user_id=message.from_user.id,
    )
    _audit(message.from_user.id, "export_memory", str(result.path))
    await message.answer(f"Export готов: {result.path}\nФайлов: {result.files_count}")


@router.message(Command("import_memory"))
async def import_memory_handler(message: Message) -> None:
    if message.from_user is None:
        return
    args = (message.text or "").partition(" ")[2].strip()
    if not args:
        await message.answer("Использование: /import_memory [--apply] <zip_path>")
        return
    dry_run = True
    if args.startswith("--apply "):
        dry_run = False
        args = args.partition(" ")[2].strip()
    try:
        result = import_user_memory(
            vault_path=get_settings().obsidian_vault_path,
            user_id=message.from_user.id,
            archive_path=args,
            dry_run=dry_run,
        )
    except FileNotFoundError:
        await message.answer("Архив не найден.")
        return
    _audit(message.from_user.id, "import_memory", f"dry_run={dry_run} {args}")
    mode = "Dry-run" if dry_run else "Import"
    await message.answer(f"{mode}: {result.files_count} файлов.")


@router.message(Command("orders"))
async def orders_handler(message: Message) -> None:
    if message.from_user is None:
        return
    orders = StandingOrderStore(get_settings().obsidian_vault_path).list_orders(
        user_id=message.from_user.id
    )
    if not orders:
        await message.answer("Standing orders пока нет.")
        return
    await message.answer("\n".join(f"- {order.id}: {order.text}" for order in orders)[:3900])


@router.message(Command("order_add"))
async def order_add_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /order_add <инструкция>")
        return
    order = StandingOrderStore(get_settings().obsidian_vault_path).add_order(
        user_id=message.from_user.id,
        text=text,
    )
    _audit(message.from_user.id, "order_add", order.id)
    await message.answer(f"Standing order сохранён. ID: {order.id}")


@router.message(Command("order_delete"))
async def order_delete_handler(message: Message) -> None:
    if message.from_user is None:
        return
    order_id = (message.text or "").partition(" ")[2].strip()
    if not order_id:
        await message.answer("Использование: /order_delete <id>")
        return
    deleted = StandingOrderStore(get_settings().obsidian_vault_path).delete_order(
        user_id=message.from_user.id,
        order_id=order_id,
    )
    if deleted:
        _audit(message.from_user.id, "order_delete", order_id)
    await message.answer("Standing order удалён." if deleted else "Standing order не найден.")


@router.message(Command("inbox_review"))
async def inbox_review_handler(message: Message) -> None:
    if message.from_user is None:
        return
    notes = ObsidianMemory(get_settings().obsidian_vault_path).inbox_review(
        user_id=message.from_user.id
    )
    if not notes:
        await message.answer("Inbox review: необработанных заметок не найдено.")
        return
    lines = ["Inbox review:"]
    lines.extend(
        f"{index}. {note.snippet}\nID: {note.path.stem}"
        for index, note in enumerate(notes, 1)
    )
    await message.answer("\n\n".join(lines)[:3900])


@router.message(Command("session_summary"))
async def session_summary_handler(message: Message) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user)
        rows = await session.execute(
            select(BotMessage.text)
            .join(BotSession, BotSession.id == BotMessage.session_id)
            .where(BotSession.user_id == user.id)
            .order_by(desc(BotMessage.created_at))
            .limit(30)
        )
        await session.commit()
    messages = [text for text in reversed(rows.scalars().all()) if text]
    summary = summarize_conversation(messages)
    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    path = memory.remember_user_note(
        user_id=message.from_user.id,
        text=summary.body,
        note_type="conversation",
        extra_tags=["conversation", "summary"],
        title=summary.title,
    )
    _audit(message.from_user.id, "session_summary", path.name)
    await message.answer(f"Сводка сессии сохранена: {path.name}")


@router.message(Command("compact"))
async def compact_handler(message: Message) -> None:
    await session_summary_handler(message)


@router.message(Command("status"))
async def status_handler(message: Message) -> None:
    if message.from_user is None:
        return
    settings = get_settings()
    user_id = message.from_user.id
    runtime = AssistantRuntimeStore(settings.obsidian_vault_path)
    state = runtime.get_state(user_id=user_id)
    memory = ObsidianMemory(settings.obsidian_vault_path)
    mini = mini_app_manifest(settings.tg_mini_app_url)
    jobs_count = len(AssistantJobStore(settings.obsidian_vault_path).list_jobs(user_id=user_id))
    orders_count = len(
        StandingOrderStore(settings.obsidian_vault_path).list_orders(user_id=user_id)
    )
    active_skill = AssistantSkillStore(settings.obsidian_vault_path).active_skill_name(
        user_id=user_id
    )
    lines = [
        "Assistant status",
        f"Mode: {state.mode}",
        f"Trace: {'on' if state.trace_enabled else 'off'}",
        f"Verbose: {'on' if state.verbose_enabled else 'off'}",
        f"Session epoch: {state.session_epoch}",
        f"Active space: {memory.get_active_space(user_id)}",
        f"Active skill: {active_skill}",
        f"Jobs: {jobs_count}",
        f"Standing orders: {orders_count}",
        f"Mini App: {'enabled' if mini.enabled else 'url not set'}",
    ]
    await message.answer("\n".join(lines))


@router.message(Command("mode"))
async def mode_handler(message: Message) -> None:
    if message.from_user is None:
        return
    mode = (message.text or "").partition(" ")[2].strip()
    settings = get_settings()
    runtime = AssistantRuntimeStore(settings.obsidian_vault_path)
    if not mode:
        state = runtime.get_state(user_id=message.from_user.id)
        await message.answer(
            f"Режим ассистента: {state.mode}\nДоступные: {', '.join(ASSISTANT_MODES)}"
        )
        return
    try:
        state = runtime.set_mode(user_id=message.from_user.id, mode=mode)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    _audit(message.from_user.id, "mode", state.mode)
    await message.answer(f"Режим ассистента: {state.mode}")


@router.message(Command("trace"))
async def trace_handler(message: Message) -> None:
    if message.from_user is None:
        return
    value = (message.text or "").partition(" ")[2].strip()
    if not value:
        state = AssistantRuntimeStore(get_settings().obsidian_vault_path).get_state(
            user_id=message.from_user.id
        )
        await message.answer(f"Trace: {'on' if state.trace_enabled else 'off'}")
        return
    try:
        enabled = parse_on_off(value)
    except ValueError:
        await message.answer("Использование: /trace on|off")
        return
    state = AssistantRuntimeStore(get_settings().obsidian_vault_path).set_trace(
        user_id=message.from_user.id,
        enabled=enabled,
    )
    _audit(message.from_user.id, "trace", str(enabled))
    await message.answer(f"Trace: {'on' if state.trace_enabled else 'off'}")


@router.message(Command("verbose"))
async def verbose_handler(message: Message) -> None:
    if message.from_user is None:
        return
    value = (message.text or "").partition(" ")[2].strip()
    if not value:
        state = AssistantRuntimeStore(get_settings().obsidian_vault_path).get_state(
            user_id=message.from_user.id
        )
        await message.answer(f"Verbose: {'on' if state.verbose_enabled else 'off'}")
        return
    try:
        enabled = parse_on_off(value)
    except ValueError:
        await message.answer("Использование: /verbose on|off")
        return
    state = AssistantRuntimeStore(get_settings().obsidian_vault_path).set_verbose(
        user_id=message.from_user.id,
        enabled=enabled,
    )
    _audit(message.from_user.id, "verbose", str(enabled))
    await message.answer(f"Verbose: {'on' if state.verbose_enabled else 'off'}")


@router.message(Command("session_reset"))
async def session_reset_handler(message: Message) -> None:
    if message.from_user is None:
        return
    state = AssistantRuntimeStore(get_settings().obsidian_vault_path).reset_session(
        user_id=message.from_user.id
    )
    _audit(message.from_user.id, "session_reset", str(state.session_epoch))
    await message.answer(f"Сессия сброшена. Epoch: {state.session_epoch}")


@router.message(Command("new"))
async def new_session_handler(message: Message) -> None:
    await session_reset_handler(message)


@router.message(Command("usage"))
async def usage_handler(message: Message) -> None:
    if message.from_user is None:
        return
    settings = get_settings()
    user_id = message.from_user.id
    memory = ObsidianMemory(settings.obsidian_vault_path)
    skills = AssistantSkillStore(settings.obsidian_vault_path)
    jobs = AssistantJobStore(settings.obsidian_vault_path, timezone_name=settings.timezone)
    state = AssistantRuntimeStore(settings.obsidian_vault_path).get_state(user_id=user_id)
    lines = [
        "Usage",
        f"Mode: {state.mode}",
        f"Trace: {'on' if state.trace_enabled else 'off'}",
        f"Verbose: {'on' if state.verbose_enabled else 'off'}",
        f"Session epoch: {state.session_epoch}",
        f"Recent notes: {len(memory.recent_notes(user_id=user_id, limit=1000))}",
        f"Open tasks: {len(memory.list_open_tasks(user_id=user_id, limit=1000))}",
        f"Reminders: {len(memory.list_reminders(user_id=user_id, limit=1000))}",
        f"Skills: {len(skills.list_skills())}",
        f"Jobs: {len(jobs.list_jobs(user_id=user_id))}",
    ]
    await message.answer("\n".join(lines))


@router.message(Command("skills"))
async def skills_handler(message: Message) -> None:
    if message.from_user is None:
        return
    store = AssistantSkillStore(get_settings().obsidian_vault_path)
    active = store.active_skill_name(user_id=message.from_user.id)
    skills = store.list_skills()
    lines = ["Skills:"]
    for skill in skills:
        marker = "*" if skill.name == active else "-"
        lines.append(f"{marker} {skill.name}: {skill.description}")
    await message.answer("\n".join(lines)[:3900])


@router.message(Command("skill"))
async def skill_handler(message: Message) -> None:
    if message.from_user is None:
        return
    name = (message.text or "").partition(" ")[2].strip()
    store = AssistantSkillStore(get_settings().obsidian_vault_path)
    if not name:
        active = store.active_skill_name(user_id=message.from_user.id)
        await message.answer(f"Активный skill: {active or 'не выбран'}")
        return
    try:
        skill = store.set_active_skill(user_id=message.from_user.id, name=name)
    except ValueError:
        await message.answer("Skill не найден. Посмотри список через /skills.")
        return
    _audit(message.from_user.id, "skill", skill.name)
    await message.answer(f"Активный skill: {skill.name}")


@router.message(Command("skill_add"))
async def skill_add_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    name, _, instructions = text.partition(" ")
    if not name or not instructions.strip():
        await message.answer("Использование: /skill_add <name> <instructions>")
        return
    try:
        skill = AssistantSkillStore(get_settings().obsidian_vault_path).create_skill(
            name=name,
            instructions=instructions,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    _audit(message.from_user.id, "skill_add", skill.name)
    await message.answer(f"Skill создан: {skill.name}")


@router.message(Command("job_add"))
async def job_add_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    try:
        schedule_type, schedule_value, delivery_mode, job_message = parse_job_request(text)
        settings = get_settings()
        job = AssistantJobStore(
            settings.obsidian_vault_path,
            timezone_name=settings.timezone,
        ).add_job(
            user_id=message.from_user.id,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            message=job_message,
            delivery_mode=delivery_mode,
        )
    except ValueError as exc:
        await message.answer(str(exc))
        return
    local_next = job.next_run_at.astimezone(ZoneInfo(get_settings().timezone))
    _audit(message.from_user.id, "job_add", f"{job.id} {job.delivery_mode}")
    await message.answer(
        f"Job создан. ID: {job.id}\nMode: {job.delivery_mode}\n"
        f"Следующий запуск: {local_next:%Y-%m-%d %H:%M}"
    )


@router.message(Command("jobs"))
async def jobs_handler(message: Message) -> None:
    if message.from_user is None:
        return
    settings = get_settings()
    timezone = ZoneInfo(settings.timezone)
    job_store = AssistantJobStore(settings.obsidian_vault_path, timezone_name=settings.timezone)
    jobs = job_store.list_jobs(user_id=message.from_user.id)
    if not jobs:
        await message.answer("Jobs пока нет.")
        return
    lines = ["Jobs:"]
    for job in jobs:
        status = "on" if job.enabled else "off"
        next_at = job.next_run_at.astimezone(timezone)
        lines.append(
            f"- {job.id} [{status}/{job.delivery_mode}] {job.schedule_type} {job.schedule_value} "
            f"{next_at:%Y-%m-%d %H:%M}: {job.message}"
        )
    await message.answer("\n".join(lines)[:3900])


@router.message(Command("job_runs"))
async def job_runs_handler(message: Message) -> None:
    if message.from_user is None:
        return
    settings = get_settings()
    timezone = ZoneInfo(settings.timezone)
    job_store = AssistantJobStore(settings.obsidian_vault_path, timezone_name=settings.timezone)
    runs = job_store.list_runs(user_id=message.from_user.id)
    if not runs:
        await message.answer("Запусков jobs пока нет.")
        return
    lines = ["Job runs:"]
    for run in runs:
        status = "OK" if run.ok else "FAIL"
        ran_at = run.ran_at.astimezone(timezone)
        lines.append(f"- {ran_at:%Y-%m-%d %H:%M} {status} {run.job_id}: {run.detail}")
    await message.answer("\n".join(lines)[:3900])


@router.message(Command("job_delete"))
async def job_delete_handler(message: Message) -> None:
    if message.from_user is None:
        return
    job_id = (message.text or "").partition(" ")[2].strip()
    if not job_id:
        await message.answer("Использование: /job_delete <job_id>")
        return
    settings = get_settings()
    deleted = AssistantJobStore(
        settings.obsidian_vault_path,
        timezone_name=settings.timezone,
    ).delete_job(user_id=message.from_user.id, job_id=job_id)
    if deleted:
        _audit(message.from_user.id, "job_delete", job_id)
    await message.answer("Job удалён." if deleted else "Job не найден.")


@router.message(Command("tasks"))
async def tasks_handler(message: Message) -> None:
    if message.from_user is None:
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    tasks = memory.list_open_tasks(user_id=message.from_user.id)
    if not tasks:
        await message.answer("Открытых задач в памяти пока нет.")
        return
    lines = ["Открытые задачи:"]
    lines.extend(
        f"{index}. {task.snippet}\nID: {task.id}"
        for index, task in enumerate(tasks, start=1)
    )
    await message.answer("\n\n".join(lines))


@router.message(Command("today_tasks"))
async def today_tasks_handler(message: Message) -> None:
    await tasks_handler(message)


@router.message(Command("task_search"))
async def task_search_handler(message: Message) -> None:
    if message.from_user is None:
        return
    query = (message.text or "").partition(" ")[2].strip()
    if not query:
        await message.answer("Использование: /task_search <запрос>")
        return
    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    results = memory.filtered_search(user_id=message.from_user.id, query=f"type:task {query}")
    if not results:
        await message.answer("Задачи не найдены.")
        return
    lines = ["Задачи:"]
    lines.extend(
        f"{index}. {result.snippet}\nID: {result.path.stem}"
        for index, result in enumerate(results, 1)
    )
    await message.answer("\n\n".join(lines)[:3900])


@router.message(Command("task_tag"))
async def task_tag_handler(message: Message) -> None:
    if message.from_user is None:
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /task_tag <task_id> <tag>")
        return
    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    tagged = memory.add_note_tag(user_id=message.from_user.id, note_id=parts[1], tag=parts[2])
    if tagged:
        _audit(message.from_user.id, "task_tag", f"{parts[1]} {parts[2]}")
    await message.answer("Тег добавлен." if tagged else "Задача не найдена.")


@router.message(Command("task_due"))
async def task_due_handler(message: Message) -> None:
    if message.from_user is None:
        return
    args = (message.text or "").partition(" ")[2].strip()
    task_id, _, reminder_text = args.partition(" ")
    if not task_id or not reminder_text:
        await message.answer("Использование: /task_due <task_id> <когда> <текст>")
        return
    settings = get_settings()
    try:
        due_at, body = parse_reminder_request(reminder_text, timezone_name=settings.timezone)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    memory = ObsidianMemory(settings.obsidian_vault_path)
    path = memory.create_reminder(
        user_id=message.from_user.id,
        text=f"Task {task_id}: {body}",
        due_at=due_at,
    )
    _audit(message.from_user.id, "task_due", f"{task_id} {path.stem}")
    await message.answer(f"Due reminder создан. ID: {path.stem}")


@router.message(Command("later"))
async def later_handler(message: Message) -> None:
    await task_due_handler(message)


@router.message(Command("context"))
async def context_handler(message: Message) -> None:
    if message.from_user is None:
        return
    query = (message.text or "").partition(" ")[2].strip()
    if not query:
        await message.answer("Использование: /context <тема>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    results = memory.related_context(user_id=message.from_user.id, text=query)
    if not results:
        await message.answer("Связанный контекст не найден.")
        return
    lines = ["Связанный контекст:"]
    for index, result in enumerate(results, start=1):
        lines.append(_format_memory_result(index, result.snippet, result.citation, result.tags))
    await message.answer("\n\n".join(lines))


@router.message(Command("person"))
async def person_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /person <имя> или /person <имя>: <заметка>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    if ":" in text:
        person_name, _, person_note = text.partition(":")
        active_space = memory.get_active_space(message.from_user.id)
        space, body = parse_space_prefix(person_note, default_space=active_space)
        try:
            path = memory.remember_person_note(
                user_id=message.from_user.id,
                person_name=person_name,
                text=body,
                space=space,
            )
        except ValueError:
            await message.answer("Использование: /person <имя>: <заметка>")
            return
        await message.answer(f"Заметка о {person_name.strip()} сохранена: {path.name}")
        return

    notes = memory.person_notes(user_id=message.from_user.id, person_name=text)
    if not notes:
        await message.answer("Заметок об этом человеке пока нет.")
        return
    lines = [f"Заметки о {text}:"]
    for index, result in enumerate(notes, start=1):
        lines.append(_format_memory_result(index, result.snippet, result.citation, result.tags))
    await message.answer("\n\n".join(lines)[:3900])


@router.message(Command("decide"))
async def decide_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /decide <вопрос; вариант A; вариант B>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    active_space = memory.get_active_space(message.from_user.id)
    space, prompt = parse_space_prefix(text, default_space=active_space)
    try:
        path, related = memory.create_decision_note(
            user_id=message.from_user.id,
            prompt=prompt,
            space=space,
        )
    except ValueError:
        await message.answer("Использование: /decide <вопрос; вариант A; вариант B>")
        return
    lines = [f"Черновик решения сохранён: {path.name}"]
    if related:
        lines.append("")
        lines.append("Связанный контекст:")
        lines.extend(f"- {result.snippet}\n  {result.citation}" for result in related)
    await message.answer("\n".join(lines)[:3900])


@router.message(Command("recent"))
async def recent_handler(message: Message) -> None:
    if message.from_user is None:
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    notes = memory.recent_notes(user_id=message.from_user.id)
    if not notes:
        await message.answer("В памяти пока нет заметок.")
        return
    lines = ["Последние заметки:"]
    for index, note in enumerate(notes, start=1):
        tags = f" [{', '.join(note.tags)}]" if note.tags else ""
        lines.append(f"{index}. {note.snippet}{tags}")
    await message.answer("\n\n".join(lines)[:3900])


@router.message(Command("collections"))
async def collections_handler(message: Message) -> None:
    if message.from_user is None:
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    collections = memory.list_collections(user_id=message.from_user.id)
    if not collections:
        await message.answer("Коллекций пока нет.")
        return
    lines = ["Коллекции:"]
    lines.extend(f"- {collection.name}: {collection.count}" for collection in collections[:30])
    await message.answer("\n".join(lines))


@router.message(Command("collection"))
async def collection_handler(message: Message) -> None:
    if message.from_user is None:
        return
    collection = (message.text or "").partition(" ")[2].strip()
    if not collection:
        await message.answer("Использование: /collection <название>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    notes = memory.collection_notes(user_id=message.from_user.id, collection=collection)
    if not notes:
        await message.answer("В этой коллекции пока нет заметок.")
        return
    lines = [f"Коллекция {collection}:"]
    for index, note in enumerate(notes, start=1):
        tags = f" [{', '.join(note.tags)}]" if note.tags else ""
        lines.append(f"{index}. {note.snippet}{tags}")
    await message.answer("\n\n".join(lines)[:3900])


@router.message(Command("pin"))
async def pin_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /pin <важная заметка>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    active_space = memory.get_active_space(message.from_user.id)
    space, body = parse_space_prefix(text, default_space=active_space)
    path = memory.remember_user_note(
        user_id=message.from_user.id,
        text=body,
        note_type="important",
        extra_tags=["important"],
        space=space,
    )
    await message.answer(f"Закрепил: {path.name}")


@router.message(Command("pins"))
async def pins_handler(message: Message) -> None:
    if message.from_user is None:
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    pins = memory.list_pins(user_id=message.from_user.id)
    if not pins:
        await message.answer("Важных заметок пока нет.")
        return
    lines = ["Важное:"]
    lines.extend(f"{index}. {pin.snippet}" for index, pin in enumerate(pins, start=1))
    await message.answer("\n\n".join(lines)[:3900])


@router.message(Command("done"))
async def done_handler(message: Message) -> None:
    if message.from_user is None:
        return
    task_ref = (message.text or "").partition(" ")[2].strip()
    if not task_ref:
        await message.answer("Использование: /done <ID задачи или номер из /tasks>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    task_id = task_ref
    if task_ref.isdigit():
        tasks = memory.list_open_tasks(user_id=message.from_user.id)
        index = int(task_ref) - 1
        if 0 <= index < len(tasks):
            task_id = tasks[index].id
    if not memory.complete_task(user_id=message.from_user.id, task_id=task_id):
        await message.answer("Не нашел такую открытую задачу.")
        return
    await message.answer("Готово. Задача закрыта.")


@router.message(Command("remind"))
async def remind_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    settings = get_settings()
    try:
        due_at, body = parse_reminder_request(text, timezone_name=settings.timezone)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    memory = ObsidianMemory(settings.obsidian_vault_path)
    path = memory.create_reminder(
        user_id=message.from_user.id,
        text=body,
        due_at=due_at,
        space=memory.get_active_space(message.from_user.id),
    )
    local_due_at = due_at.astimezone(ZoneInfo(settings.timezone))
    await message.answer(f"Напомню {local_due_at:%Y-%m-%d %H:%M}. ID: {path.stem}")


@router.message(Command("reminders"))
async def reminders_handler(message: Message) -> None:
    if message.from_user is None:
        return

    settings = get_settings()
    timezone = ZoneInfo(settings.timezone)
    memory = ObsidianMemory(settings.obsidian_vault_path)
    reminders = memory.list_reminders(user_id=message.from_user.id)
    if not reminders:
        await message.answer("Активных напоминаний нет.")
        return
    lines = ["Напоминания:"]
    for index, reminder in enumerate(reminders, start=1):
        due_at = reminder.due_at.astimezone(timezone)
        lines.append(
            f"{index}. {due_at:%Y-%m-%d %H:%M} - {reminder.snippet}\nID: {reminder.id}"
        )
    await message.answer("\n\n".join(lines)[:3900])


@router.message(Command("spaces"))
async def spaces_handler(message: Message) -> None:
    if message.from_user is None:
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    spaces = memory.list_spaces(user_id=message.from_user.id)
    lines = ["Spaces:"]
    for space in spaces:
        marker = "*" if space.active else "-"
        lines.append(f"{marker} {space.name}: {space.count}")
    await message.answer("\n".join(lines))


@router.message(Command("space"))
async def space_handler(message: Message) -> None:
    if message.from_user is None:
        return
    space = (message.text or "").partition(" ")[2].strip()
    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    if not space:
        await message.answer(f"Активный space: {memory.get_active_space(message.from_user.id)}")
        return
    active = memory.set_active_space(user_id=message.from_user.id, space=space)
    await message.answer(f"Активный space: {active}")


@router.message(Command("sources"))
async def sources_handler(message: Message) -> None:
    if message.from_user is None:
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    sources = memory.list_sources(user_id=message.from_user.id)
    if not sources:
        await message.answer("Источников пока нет.")
        return
    lines = ["Источники:"]
    for index, source in enumerate(sources, start=1):
        url = f"\n{source.source_url}" if source.source_url else ""
        lines.append(f"{index}. {source.title} [{source.source_type}, {source.space}]{url}")
    await message.answer("\n\n".join(lines)[:3900])


@router.message(Command("source_trust"))
async def source_trust_handler(message: Message) -> None:
    if message.from_user is None:
        return
    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    trust = build_source_trust(memory.list_sources(user_id=message.from_user.id, limit=500))
    await message.answer(format_source_trust(trust)[:3900])


@router.message(Command("tools"))
async def tools_handler(message: Message) -> None:
    lines = ["Tools:"]
    lines.extend(f"- {tool.name}: {tool.description}" for tool in list_tools())
    await message.answer("\n".join(lines))


@router.message(Command("tool"))
async def tool_handler(message: Message) -> None:
    text = (message.text or "").partition(" ")[2].strip()
    name, _, payload = text.partition(" ")
    if not name:
        await message.answer("Использование: /tool <name> <input>")
        return
    try:
        result = run_tool(name=name, text=payload, timezone_name=get_settings().timezone)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await message.answer(str(result)[:3900])


@router.message(Command("mini_app"))
async def mini_app_handler(message: Message) -> None:
    if not is_feature_enabled("miniapp"):
        await message.answer("Mini App отключён в конфигурации.")
        return
    manifest = mini_app_manifest(get_settings().tg_mini_app_url)
    if not manifest.enabled:
        await message.answer(format_mini_app_status(manifest))
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Open Mini App",
                    web_app=WebAppInfo(url=manifest.url),
                )
            ]
        ]
    )
    await message.answer(format_mini_app_status(manifest), reply_markup=keyboard)


@router.message(Command("assistant_capabilities"))
async def assistant_capabilities_handler(message: Message) -> None:
    lines = ["Assistant capabilities:"]
    for capability in assistant_capabilities():
        mark = "ON" if capability.enabled else "OFF"
        lines.append(f"- {mark} {capability.name}: {capability.description}")
    await message.answer("\n".join(lines))


@router.message(Command("delete_memory"))
async def delete_memory_handler(message: Message) -> None:
    if message.from_user is None:
        return
    note_id = (message.text or "").partition(" ")[2].strip()
    if not note_id:
        await message.answer("Использование: /delete_memory <note_id>")
        return

    settings = get_settings()
    approval = ActionApprovalStore(settings.obsidian_vault_path).create(
        user_id=message.from_user.id,
        action="delete_memory",
        payload={"note_id": note_id},
        ttl_minutes=settings.assistant_approval_ttl_minutes,
    )
    _audit(message.from_user.id, "delete_memory_request", note_id)
    await message.answer(
        "Удаление требует подтверждения.\n"
        f"Отправь /approve {approval.id}, чтобы удалить заметку {note_id}."
    )


@router.message(Command("approve"))
async def approve_handler(message: Message) -> None:
    if message.from_user is None:
        return
    approval_id = (message.text or "").partition(" ")[2].strip()
    if not approval_id:
        await message.answer("Использование: /approve <code>")
        return

    settings = get_settings()
    store = ActionApprovalStore(settings.obsidian_vault_path)
    action = store.consume(user_id=message.from_user.id, approval_id=approval_id)
    if action is None:
        await message.answer("Подтверждение не найдено или истекло.")
        return
    memory = ObsidianMemory(settings.obsidian_vault_path)
    if action.action == "delete_memory":
        deleted = memory.delete_note(
            user_id=message.from_user.id,
            note_id=action.payload.get("note_id", ""),
        )
        _audit(message.from_user.id, "delete_memory", action.payload.get("note_id", ""))
        await message.answer("Заметка удалена." if deleted else "Заметка не найдена.")
        return
    await message.answer("Неизвестное действие.")


@router.message(Command("remember"))
async def remember_handler(message: Message) -> None:
    if message.from_user is None:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Использование: /remember <что запомнить>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    active_space = memory.get_active_space(message.from_user.id)
    space, body = parse_space_prefix(text, default_space=active_space)
    path = memory.remember_user_note(user_id=message.from_user.id, text=body, space=space)
    await message.answer(f"Запомнил: {path.name}")


@router.message(Command("memory"))
async def memory_search_handler(message: Message) -> None:
    if message.from_user is None:
        return
    query = (message.text or "").partition(" ")[2].strip()
    if not query:
        await message.answer("Использование: /memory <что найти>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    results = memory.filtered_search(user_id=message.from_user.id, query=query)
    if not results:
        await message.answer("В памяти ничего не нашел.")
        return

    lines = ["Нашел в памяти:"]
    for index, result in enumerate(results, start=1):
        lines.append(_format_memory_result(index, result.snippet, result.citation, result.tags))
    await message.answer("\n\n".join(lines))


@router.message(Command("ask"))
async def memory_ask_handler(message: Message) -> None:
    if message.from_user is None:
        return
    question = (message.text or "").partition(" ")[2].strip()
    if not question:
        await message.answer("Использование: /ask <вопрос к памяти>")
        return

    memory = ObsidianMemory(get_settings().obsidian_vault_path)
    await message.answer(memory.ask_user_memory(user_id=message.from_user.id, question=question))


@router.message(Command("learn_url"))
async def learn_url_handler(message: Message) -> None:
    if message.from_user is None:
        return
    url = (message.text or "").partition(" ")[2].strip()
    if not url:
        await message.answer("Использование: /learn_url <ссылка>")
        return

    settings = get_settings()
    try:
        page = await fetch_page_summary(url)
    except Exception as exc:
        await message.answer(f"Не удалось прочитать ссылку: {str(exc)[:300]}")
        return

    memory = ObsidianMemory(settings.obsidian_vault_path)
    memory.remember_user_note(
        user_id=message.from_user.id,
        text=format_learned_page_note(page),
        source_type="web",
        source_url=url,
        title=page.title,
    )
    await message.answer(f"Сохранил в память: {page.title}")


@router.message(Command("rss_add"))
async def rss_add_handler(message: Message) -> None:
    if message.from_user is None:
        return
    feed_url = (message.text or "").partition(" ")[2].strip()
    if not feed_url:
        await message.answer("Использование: /rss_add <rss-or-atom-url>")
        return

    try:
        path = add_rss_subscription(
            get_settings().obsidian_vault_path,
            user_id=message.from_user.id,
            feed_url=feed_url,
        )
    except Exception as exc:
        await message.answer(f"Не удалось добавить RSS: {str(exc)[:300]}")
        return
    await message.answer(f"RSS добавлен: {path.name}")


@router.message(Command("rss_digest"))
async def rss_digest_handler(message: Message) -> None:
    if message.from_user is None:
        return
    settings = get_settings()
    subscriptions = list_rss_subscriptions(
        settings.obsidian_vault_path,
        user_id=message.from_user.id,
    )
    if not subscriptions:
        await message.answer("RSS-подписок пока нет. Добавь через /rss_add <url>.")
        return

    digests = await fetch_feed_digests(subscriptions, limit_per_feed=3)
    text = format_feed_digests(digests)
    memory = ObsidianMemory(settings.obsidian_vault_path)
    memory.remember_user_note(user_id=message.from_user.id, text=format_digest_memory_note(digests))
    await message.answer(text[:3900])


@router.message(F.text, ~F.text.startswith("/"))
async def default_text_capture_handler(message: Message) -> None:
    text = (message.text or "").strip()
    if not text:
        return
    await _capture_text(message, text)
