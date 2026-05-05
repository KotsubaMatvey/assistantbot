from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.basket_parser import parse_basket
from app.services.obsidian_memory import ObsidianMemory, classify_note


def test_remember_user_note_writes_organized_markdown_files(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))

    path = memory.remember_user_note(
        user_id=123,
        text="У пользователя есть карта Магнита.",
        created_at=datetime(2026, 5, 6, 12, 30, tzinfo=UTC),
    )

    assert path == tmp_path / "users" / "123" / "notes" / "20260506-123000-000000.md"
    text = path.read_text(encoding="utf-8")
    assert "type: preference" in text
    assert "tags: [pricebot, memory, preference, loyalty, magnit]" in text
    assert "У пользователя есть карта Магнита." in text
    assert (tmp_path / "users" / "123" / "daily" / "2026-05-06.md").exists()
    assert (tmp_path / "users" / "123" / "profile.md").exists()
    assert (tmp_path / "inbox" / "2026-05-06.md").exists()


def test_classify_note_detects_tasks_links_and_store_tags() -> None:
    task = classify_note("Нужно проверить акции в SPAR")
    link = classify_note("Исследование цен https://example.com")

    assert task.note_type == "task"
    assert "spar" in task.tags
    assert link.note_type == "link"
    assert "link" in link.tags


def test_search_user_notes_uses_synonyms_and_keeps_users_separate(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    memory.remember_user_note(user_id=123, text="У пользователя есть карта Магнита.")
    memory.remember_user_note(user_id=456, text="Молоко другого пользователя не видно.")

    results = memory.search_user_notes(user_id=123, query="скидочные карты")

    assert results
    assert any("карта Магнита" in result.snippet for result in results)
    assert all("другого пользователя" not in result.snippet for result in results)


def test_ask_user_memory_answers_from_matching_notes(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    memory.remember_user_note(user_id=123, text="Предпочитаю молоко 2.5 по акции.")

    answer = memory.ask_user_memory(user_id=123, question="что я писал про молоко")

    assert "По памяти нашел:" in answer
    assert "молоко 2.5" in answer


def test_basket_memory_tracks_frequent_items(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    items = parse_basket("молоко 1 л\nсахар 1 кг")
    memory.remember_basket(user_id=123, raw_text="молоко 1 л\nсахар 1 кг", items=items)
    memory.remember_basket(user_id=123, raw_text="молоко 1 л\nсахар 1 кг", items=items)

    context = memory.build_price_context(user_id=123, items=parse_basket("молоко 1 л"))

    assert context.frequent_items == ["молоко"]


def test_settings_with_memory_uses_remembered_loyalty_cards(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    memory.remember_user_note(user_id=123, text="У меня есть карта Магнита.")
    memory.remember_user_note(user_id=123, text="Не люблю SPAR.")
    context = memory.build_price_context(user_id=123, items=parse_basket("молоко 1 л"))
    settings = SimpleNamespace(
        enabled_store_slugs=["smart", "magnit"],
        comparison_mode="mixed",
        has_smart_card=False,
        has_magnit_card=False,
    )

    effective = memory.settings_with_memory(settings, context)

    assert effective.has_magnit_card is True
    assert effective.has_smart_card is False
    assert "spar" in context.disliked_stores
    assert "magnit" not in context.disliked_stores


def test_price_heads_up_mentions_memory_context(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    memory.remember_user_note(user_id=123, text="У меня есть карта Магнита.")
    context = memory.build_price_context(user_id=123, items=parse_basket("молоко 1 л"))
    settings = SimpleNamespace(has_magnit_card=False)

    text = memory.format_price_heads_up(context=context, original_settings=settings)

    assert "Память:" in text
    assert "Магнит" in text
