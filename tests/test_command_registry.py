from __future__ import annotations

from app.bot.commands import help_text, public_command_defs, resolve_command


def test_public_bot_commands_exclude_admin_commands() -> None:
    commands = {command.name for command in public_command_defs()}
    assert "prices" in commands
    assert "last" in commands
    assert "remember" in commands
    assert "memory" in commands
    assert "ask" in commands
    assert "learn_url" in commands
    assert "rss_add" in commands
    assert "rss_digest" in commands
    assert "admin_status" not in commands


def test_help_text_can_include_admin_commands() -> None:
    public_text = help_text()
    admin_text = help_text(include_admin=True)
    assert "/admin_status" not in public_text
    assert "/admin_status" in admin_text
    assert "/admin_diag" in admin_text


def test_resolve_command_accepts_slash_prefix() -> None:
    command = resolve_command("/prices")
    assert command is not None
    assert command.name == "prices"
