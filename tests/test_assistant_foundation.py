from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.db.repositories.sessions import build_session_key
from app.services.access_control import AccessControlStore
from app.services.action_approvals import ActionApprovalStore
from app.services.assistant_contract import assistant_capabilities, build_thread_snapshot
from app.services.assistant_jobs import AssistantJobStore
from app.services.assistant_runtime import AssistantRuntimeStore, parse_on_off
from app.services.assistant_skills import AssistantSkillStore
from app.services.obsidian_memory import ObsidianMemory, parse_space_prefix


def test_spaces_can_be_set_and_used_for_capture(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))

    assert memory.get_active_space(123) == "default"
    assert memory.set_active_space(user_id=123, space="Work Notes") == "work-notes"
    path = memory.remember_user_note(user_id=123, text="project roadmap", space="work")

    spaces = {space.name: space for space in memory.list_spaces(user_id=123)}

    assert path.exists()
    assert spaces["work"].count == 1
    assert spaces["work-notes"].active is True
    assert parse_space_prefix("@home buy milk", default_space="work") == ("home", "buy milk")
    assert parse_space_prefix("plain note", default_space="work") == ("work", "plain note")


def test_sources_metadata_dedupe_and_citations(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))

    first = memory.remember_user_note(
        user_id=123,
        text="alpha source body",
        source_type="web",
        source_url="https://example.com/a",
        title="Alpha",
        created_at=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
    )
    second = memory.remember_user_note(
        user_id=123,
        text="alpha source body",
        source_type="web",
        source_url="https://example.com/a",
        title="Alpha duplicate",
        created_at=datetime(2026, 5, 6, 12, 1, tzinfo=UTC),
    )

    sources = memory.list_sources(user_id=123)
    results = memory.search_user_notes(user_id=123, query="alpha")

    assert first == second
    assert len(sources) == 1
    assert sources[0].source_type == "web"
    assert results[0].source_url == "https://example.com/a"
    assert "Alpha" in results[0].citation


def test_sqlite_fts_searches_child_chunks(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    long_text = "first parent paragraph\n\n" + "middle words " * 160 + "\n\nfinal unique needle"
    memory.remember_user_note(user_id=123, text=long_text, title="Chunked")

    results = memory.search_user_notes(user_id=123, query="unique needle")

    assert results
    assert results[0].chunk_no >= 1
    assert "needle" in results[0].snippet


def test_delete_note_requires_approval_store_roundtrip(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    path = memory.remember_user_note(user_id=123, text="temporary note")
    approvals = ActionApprovalStore(str(tmp_path))
    pending = approvals.create(
        user_id=123,
        action="delete_memory",
        payload={"note_id": path.stem},
        now=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
    )

    action = approvals.consume(
        user_id=123,
        approval_id=pending.id,
        now=datetime(2026, 5, 6, 12, 1, tzinfo=UTC),
    )

    assert action is not None
    assert memory.delete_note(user_id=123, note_id=action.payload["note_id"]) is True
    assert not path.exists()


def test_pairing_code_adds_user_to_allowlist(tmp_path) -> None:
    access = AccessControlStore(str(tmp_path))
    pairing = access.create_pairing_code(
        user_id=456,
        now=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
    )

    assert access.is_allowed(user_id=456, mode="pairing", admin_ids=[]) is False
    assert access.approve_pairing_code(
        code=pairing.code.lower(),
        now=datetime(2026, 5, 6, 12, 1, tzinfo=UTC),
    ) == 456
    assert access.is_allowed(user_id=456, mode="pairing", admin_ids=[]) is True


def test_pairing_code_reuses_active_code(tmp_path) -> None:
    access = AccessControlStore(str(tmp_path))

    first = access.create_pairing_code(
        user_id=456,
        now=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
    )
    second = access.create_pairing_code(
        user_id=456,
        now=datetime(2026, 5, 6, 12, 1, tzinfo=UTC),
    )

    assert second.code == first.code


def test_runtime_state_tracks_mode_flags_and_session_epoch(tmp_path) -> None:
    runtime = AssistantRuntimeStore(str(tmp_path))

    assert runtime.get_state(user_id=123).mode == "secretary"
    assert runtime.set_mode(user_id=123, mode="researcher").mode == "researcher"
    assert runtime.set_trace(user_id=123, enabled=True).trace_enabled is True
    assert runtime.set_verbose(user_id=123, enabled=True).verbose_enabled is True
    assert runtime.reset_session(user_id=123).session_epoch == 1
    assert build_session_key(
        platform="telegram",
        chat_id=10,
        user_id=123,
        session_epoch=1,
    ).endswith(":epoch:1")
    assert parse_on_off("on") is True
    assert parse_on_off("off") is False


def test_skill_store_creates_defaults_and_custom_skill(tmp_path) -> None:
    store = AssistantSkillStore(str(tmp_path))

    skills = {skill.name for skill in store.list_skills()}
    custom = store.create_skill(name="Draft Coach", instructions="Review drafts tersely.")
    active = store.set_active_skill(user_id=123, name="draft-coach")

    assert "secretary" in skills
    assert custom.path.exists()
    assert active.name == "draft-coach"
    assert store.active_skill_name(user_id=123) == "draft-coach"


def test_job_store_schedules_runs_and_deletes_jobs(tmp_path) -> None:
    store = AssistantJobStore(str(tmp_path), timezone_name="Europe/Moscow")
    now = datetime(2026, 5, 6, 6, 0, tzinfo=UTC)

    job = store.add_job(
        user_id=123,
        schedule_type="daily",
        schedule_value="09:30",
        message="morning brief",
        now=now,
    )
    due = store.due_jobs(now=datetime(2026, 5, 6, 6, 30, tzinfo=UTC))
    updated = store.record_run(job=job, ok=True, detail="delivered", now=job.next_run_at)

    assert job.next_run_at.astimezone(ZoneInfo("Europe/Moscow")).hour == 9
    assert [item.id for item in due] == [job.id]
    assert updated.next_run_at > job.next_run_at
    assert store.list_runs(user_id=123)[0].ok is True
    assert store.delete_job(user_id=123, job_id=job.id) is True


def test_assistant_contract_exposes_no_llm_capabilities(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    memory.remember_user_note(user_id=123, text="contract context")

    capabilities = {capability.name: capability.enabled for capability in assistant_capabilities()}
    snapshot = build_thread_snapshot(memory=memory, user_id=123, query="contract")

    assert capabilities["sqlite_fts_search"] is True
    assert capabilities["tool_approvals"] is True
    assert capabilities["llm_answers"] is False
    assert snapshot.active_space == "default"
    assert snapshot.context
