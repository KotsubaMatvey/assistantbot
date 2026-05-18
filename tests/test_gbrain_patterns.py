from __future__ import annotations

import json
from datetime import UTC, datetime

from app.services.object_store import ObjectStore
from app.services.obsidian_memory import ObsidianMemory


def test_brain_schema_and_person_canonical_page_are_created(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    created = datetime(2026, 5, 18, 9, 0, tzinfo=UTC)

    note_path = memory.remember_person_note(
        user_id=123,
        person_name="Ivan",
        text="Prefers short email updates.",
        created_at=created,
    )

    person_page = tmp_path / "users" / "123" / "brain" / "people" / "ivan.md"
    text = person_page.read_text(encoding="utf-8")

    assert (tmp_path / "RESOLVER.md").exists()
    assert (tmp_path / "schema.md").exists()
    assert note_path.name in text
    assert "# Person: Ivan" in text
    assert "## Current" in text
    assert "## Timeline" in text


def test_project_and_decision_canonical_pages_are_updated(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))

    memory.remember_user_note(
        user_id=123,
        text="Project alpha: decided to ship dashboard v1.",
        note_type="decision",
        extra_tags=["project-alpha"],
        title="Ship dashboard v1",
        created_at=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
    )

    project_page = tmp_path / "users" / "123" / "brain" / "projects" / "project-alpha.md"
    decision_page = (
        tmp_path / "users" / "123" / "brain" / "decisions" / "ship-dashboard-v1.md"
    )

    assert "Project alpha" in project_page.read_text(encoding="utf-8")
    assert "Ship dashboard v1" in decision_page.read_text(encoding="utf-8")


def test_source_id_search_filter_citation_and_object_relations(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))

    memory.remember_user_note(
        user_id=123,
        text="Alpha source body with unique signal.",
        source_type="github",
        source_id="src_alpha",
        source_url="https://github.com/example/alpha",
        title="Alpha Repo",
    )
    memory.remember_person_note(user_id=123, person_name="Ivan", text="Works on project alpha.")

    results = memory.filtered_search(user_id=123, query="source:src_alpha unique")
    people = ObjectStore(str(tmp_path)).list_objects(user_id=123, object_type="person")

    assert results
    assert results[0].source_id == "src_alpha"
    assert "source:src_alpha" in results[0].citation
    assert people[0].relations["person"] == "ivan"


def test_search_writes_retrieval_eval_log(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    memory.remember_user_note(user_id=123, text="Alpha launch risk is documentation.")

    assert memory.search_user_notes(user_id=123, query="alpha documentation")

    log_path = tmp_path / "users" / "123" / "evals" / "retrieval.jsonl"
    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])

    assert payload["query"] == "alpha documentation"
    assert payload["results"][0]["path"].endswith(".md")
    assert payload["latency_ms"] >= 0


def test_memory_sync_rebuilds_indexes_for_manual_markdown_edits(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    note_path = memory.remember_user_note(user_id=123, text="Original alpha text.")
    text = note_path.read_text(encoding="utf-8").replace("Original alpha", "Manual beta")
    note_path.write_text(text, encoding="utf-8")

    result = memory.sync_user_memory(user_id=123)
    results = memory.search_user_notes(user_id=123, query="manual beta")

    assert result.indexed_markdown >= 1
    assert result.indexed_objects >= 1
    assert results
    assert "Manual beta" in results[0].snippet
