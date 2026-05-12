from __future__ import annotations

from app.bot.commands import help_text, public_command_defs, resolve_command


def test_public_bot_commands_exclude_admin_commands() -> None:
    commands = {command.name for command in public_command_defs()}
    assert "prices" in commands
    assert "last" in commands
    assert "watch_price" in commands
    assert "price_alerts" in commands
    assert "price_unwatch" in commands
    assert "check_alerts" in commands
    assert "pantry" in commands
    assert "pantry_add" in commands
    assert "pantry_use" in commands
    assert "pantry_plan" in commands
    assert "pantry_deals" in commands
    assert "receipt" in commands
    assert "budget" in commands
    assert "budget_set" in commands
    assert "budget_plan" in commands
    assert "family" in commands
    assert "family_create" in commands
    assert "family_join" in commands
    assert "family_add" in commands
    assert "capture" in commands
    assert "agenda" in commands
    assert "export_memory" in commands
    assert "import_memory" in commands
    assert "orders" in commands
    assert "order_add" in commands
    assert "order_delete" in commands
    assert "inbox_review" in commands
    assert "session_summary" in commands
    assert "today_tasks" in commands
    assert "task_search" in commands
    assert "task_tag" in commands
    assert "task_due" in commands
    assert "later" in commands
    assert "source_trust" in commands
    assert "tools" in commands
    assert "tool" in commands
    assert "mini_app" in commands
    assert "markets" in commands
    assert "morning" in commands
    assert "status" in commands
    assert "new" in commands
    assert "compact" in commands
    assert "assistants" in commands
    assert "assistant_pick" in commands
    assert "automations" in commands
    assert "automation_enable" in commands
    assert "mode" in commands
    assert "trace" in commands
    assert "verbose" in commands
    assert "session_reset" in commands
    assert "usage" in commands
    assert "skills" in commands
    assert "skill" in commands
    assert "skill_add" in commands
    assert "job_add" in commands
    assert "jobs" in commands
    assert "job_runs" in commands
    assert "job_delete" in commands
    assert "preference" in commands
    assert "lifestyle_context" in commands
    assert "task" in commands
    assert "journal" in commands
    assert "digest" in commands
    assert "today" in commands
    assert "tasks" in commands
    assert "context" in commands
    assert "person" in commands
    assert "decide" in commands
    assert "recent" in commands
    assert "collections" in commands
    assert "collection" in commands
    assert "pin" in commands
    assert "pins" in commands
    assert "done" in commands
    assert "remind" in commands
    assert "reminders" in commands
    assert "voice_note" in commands
    assert "decisions" in commands
    assert "spaces" in commands
    assert "space" in commands
    assert "sources" in commands
    assert "assistant_capabilities" in commands
    assert "delete_memory" in commands
    assert "approve" in commands
    assert "remember" in commands
    assert "memory" in commands
    assert "ask" in commands
    assert "learn_url" in commands
    assert "rss_add" in commands
    assert "rss_digest" in commands
    assert "admin_status" not in commands
    assert "admin_doctor" not in commands


def test_help_text_can_include_admin_commands() -> None:
    public_text = help_text()
    admin_text = help_text(include_admin=True)
    assert "/admin_status" not in public_text
    assert "/admin_status" in admin_text
    assert "/admin_diag" in admin_text
    assert "/admin_secret_scan" in admin_text
    assert "/admin_audit" in admin_text
    assert "/admin_onboarding" in admin_text


def test_resolve_command_accepts_slash_prefix() -> None:
    command = resolve_command("/prices")
    assert command is not None
    assert command.name == "prices"
