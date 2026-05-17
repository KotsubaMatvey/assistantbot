from __future__ import annotations

from app.services.source_connectors import SourceStore, format_sources


def test_source_store_adds_lists_deduplicates_and_deletes_sources(tmp_path) -> None:
    store = SourceStore(str(tmp_path))

    first = store.add_source(
        user_id=123,
        source_type="rss",
        target="https://example.com/feed.xml",
        sync_interval_minutes=30,
    )
    duplicate = store.add_source(
        user_id=123,
        source_type="rss",
        target="https://example.com/feed.xml",
    )

    assert first.id == duplicate.id
    assert first.type == "rss"
    assert first.sync_interval_minutes == 30
    assert len(store.list_sources(user_id=123)) == 1
    assert "https://example.com/feed.xml" in format_sources(store.list_sources(user_id=123))
    assert store.delete_source(user_id=123, source_id=first.id) is True
    assert store.list_sources(user_id=123) == []


def test_source_store_normalizes_github_repo(tmp_path) -> None:
    source = SourceStore(str(tmp_path)).add_source(
        user_id=123,
        source_type="github",
        target="tinyhumansai/openhuman",
    )

    assert source.url == "https://github.com/tinyhumansai/openhuman"
