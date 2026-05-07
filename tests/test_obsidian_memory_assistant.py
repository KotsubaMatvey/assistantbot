from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.obsidian_memory import ObsidianMemory, parse_reminder_request


def test_recent_notes_returns_newest_notes_first(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    memory.remember_user_note(
        user_id=123,
        text="old note",
        created_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
    )
    memory.remember_user_note(
        user_id=123,
        text="new note",
        created_at=datetime(2026, 5, 6, 11, 0, tzinfo=UTC),
    )

    notes = memory.recent_notes(user_id=123)

    assert [note.snippet for note in notes] == ["new note", "old note"]


def test_collections_group_notes_by_type_and_tags(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    memory.remember_user_note(
        user_id=123,
        text="project alpha",
        note_type="project",
        extra_tags=["work"],
        created_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
    )
    memory.remember_user_note(
        user_id=123,
        text="project beta",
        note_type="project",
        extra_tags=["home"],
        created_at=datetime(2026, 5, 6, 11, 0, tzinfo=UTC),
    )

    collections = {
        collection.name: collection.count
        for collection in memory.list_collections(user_id=123)
    }
    work_notes = memory.collection_notes(user_id=123, collection="work")

    assert collections["project"] == 2
    assert collections["work"] == 1
    assert len(work_notes) == 1
    assert work_notes[0].snippet == "project alpha"


def test_pins_return_important_notes(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    memory.remember_user_note(
        user_id=123,
        text="regular note",
        created_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
    )
    memory.remember_user_note(
        user_id=123,
        text="keep passport number nearby",
        note_type="important",
        extra_tags=["important"],
        created_at=datetime(2026, 5, 6, 11, 0, tzinfo=UTC),
    )

    pins = memory.list_pins(user_id=123)

    assert len(pins) == 1
    assert pins[0].snippet == "keep passport number nearby"


def test_complete_task_marks_task_done(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    task_path = memory.remember_user_note(
        user_id=123,
        text="todo call bank",
        note_type="task",
        extra_tags=["task"],
        created_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
    )

    assert memory.list_open_tasks(user_id=123)
    assert memory.complete_task(user_id=123, task_id=task_path.stem) is True
    assert memory.list_open_tasks(user_id=123) == []
    assert memory.complete_task(user_id=123, task_id=task_path.stem) is False
    assert memory.complete_task(user_id=123, task_id="missing") is False


def test_parse_reminder_request_supports_relative_and_absolute_time() -> None:
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)

    relative_due_at, relative_body = parse_reminder_request(
        "через 10 минут check oven",
        now=now,
        timezone_name="Europe/Moscow",
    )
    tomorrow_due_at, tomorrow_body = parse_reminder_request(
        "завтра 09:30 buy milk",
        now=now,
        timezone_name="Europe/Moscow",
    )
    absolute_due_at, absolute_body = parse_reminder_request(
        "2026-05-08 pay invoice",
        now=now,
        timezone_name="Europe/Moscow",
    )

    assert relative_due_at == datetime(2026, 5, 6, 12, 10, tzinfo=UTC)
    assert relative_body == "check oven"
    assert tomorrow_due_at == datetime(2026, 5, 7, 6, 30, tzinfo=UTC)
    assert tomorrow_body == "buy milk"
    assert absolute_due_at == datetime(2026, 5, 8, 6, 0, tzinfo=UTC)
    assert absolute_body == "pay invoice"


def test_reminder_lifecycle_lists_due_and_marks_sent(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    created_at = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    due_at = created_at + timedelta(minutes=5)

    path = memory.create_reminder(
        user_id=123,
        text="stand up",
        due_at=due_at,
        created_at=created_at,
    )

    reminders = memory.list_reminders(user_id=123)
    assert len(reminders) == 1
    assert reminders[0].id == path.stem
    assert reminders[0].due_at == due_at
    assert memory.due_reminders(now=created_at) == []
    assert [reminder.id for reminder in memory.due_reminders(now=due_at)] == [path.stem]

    memory.mark_reminder_sent(path)

    assert memory.list_reminders(user_id=123) == []


def test_general_assistant_notes_feed_digest_and_collections(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    created_at = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)

    memory.create_task(user_id=123, text="write project proposal", created_at=created_at)
    memory.create_journal_entry(user_id=123, text="felt focused", created_at=created_at)
    memory.remember_user_note(
        user_id=123,
        text="keep passport nearby",
        note_type="important",
        extra_tags=["important"],
        created_at=created_at,
    )

    digest = memory.period_digest(user_id=123, days=2, created_at=created_at)
    journal_notes = memory.collection_notes(user_id=123, collection="journal")

    assert "Заметок: 3" in digest
    assert "task: 1" in digest
    assert "journal: 1" in digest
    assert "write project proposal" in digest
    assert len(journal_notes) == 1
    assert journal_notes[0].snippet == "felt focused"


def test_person_notes_are_searchable_by_name(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))

    path = memory.remember_person_note(
        user_id=123,
        person_name="Alex Kim",
        text="prefers concise weekly updates",
        created_at=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
    )
    notes = memory.person_notes(user_id=123, person_name="Alex Kim")

    assert path.exists()
    assert len(notes) == 1
    assert "prefers concise weekly updates" in notes[0].snippet


def test_create_decision_note_builds_template(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))

    path, related = memory.create_decision_note(
        user_id=123,
        prompt="Choose editor; VS Code; PyCharm",
        created_at=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
    )

    text = path.read_text(encoding="utf-8")
    assert related == []
    assert "type: decision" in text
    assert "## Варианты" in text
    assert "- VS Code" in text
    assert "- PyCharm" in text
