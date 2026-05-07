from __future__ import annotations

from app.bot.middlewares import should_process_group_message


def test_group_trigger_policy_requires_command_reply_or_mention() -> None:
    assert should_process_group_message(
        chat_type="private",
        text="hello",
        policy="mention",
        bot_username=None,
        is_reply_to_bot=False,
    )
    assert should_process_group_message(
        chat_type="group",
        text="/status",
        policy="mention",
        bot_username=None,
        is_reply_to_bot=False,
    )
    assert should_process_group_message(
        chat_type="group",
        text="hello @my_bot",
        policy="mention",
        bot_username="my_bot",
        is_reply_to_bot=False,
    )
    assert should_process_group_message(
        chat_type="group",
        text="hello",
        policy="mention",
        bot_username="my_bot",
        is_reply_to_bot=True,
    )
    assert not should_process_group_message(
        chat_type="group",
        text="hello",
        policy="mention",
        bot_username="my_bot",
        is_reply_to_bot=False,
    )
