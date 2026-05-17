from __future__ import annotations

from datetime import UTC, datetime

from app.services.memory_tree import MemoryTreeStore
from app.services.obsidian_memory import ObsidianMemory


def test_memory_tree_rebuild_writes_daily_weekly_profile_and_projects(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    store = MemoryTreeStore(str(tmp_path))
    created = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)

    memory.remember_user_note(
        user_id=123,
        text="Project alpha: decided to ship the first dashboard.",
        note_type="decision",
        extra_tags=["project-alpha"],
        created_at=created,
    )
    memory.remember_user_note(
        user_id=123,
        text="Project alpha: todo write release notes.",
        note_type="task",
        extra_tags=["project-alpha"],
        created_at=created,
    )
    memory.remember_user_note(
        user_id=123,
        text="Prefer concise weekly updates.",
        note_type="preference",
        created_at=created,
    )

    result = store.rebuild_tree(memory=memory, user_id=123, now=created)

    assert result.raw_captures == 3
    assert result.daily_summaries == 1
    assert result.project_summaries == 1
    assert result.profile_path.exists()
    assert result.weekly_path.exists()
    assert "Long-term memory profile" in result.profile_path.read_text(encoding="utf-8")


def test_project_summary_keeps_source_notes(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    store = MemoryTreeStore(str(tmp_path))
    memory.remember_user_note(user_id=123, text="alpha launch risk is documentation")

    text = store.project_summary(user_id=123, project="alpha launch", memory=memory)

    assert "Project summary: alpha launch" in text
    assert "Source notes" in text
    assert "documentation" in text
