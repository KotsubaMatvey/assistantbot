from __future__ import annotations

import asyncio

import app.services.knowledge_ingestion as knowledge_ingestion
import httpx
import pytest
from app.services.knowledge_ingestion import (
    add_rss_subscription,
    compact_memory_text,
    extract_page_summary,
    format_feed_digests,
    parse_feed_entries,
    prepare_memory_content,
    validate_public_url,
)


def test_extract_page_summary_removes_scripts_and_keeps_title() -> None:
    page = extract_page_summary(
        """
        <html>
          <head><title>Test page</title><script>secret()</script></head>
          <body><h1>Hello</h1><p>Useful text</p></body>
        </html>
        """,
        "https://example.com",
    )

    assert page.title == "Test page"
    assert "Useful text" in page.summary
    assert "secret" not in page.summary


def test_compact_memory_text_deduplicates_lines_and_truncates() -> None:
    text = "Alpha signal\nAlpha signal\nBeta signal needs follow up and sizing"

    compacted = compact_memory_text(text, max_chars=30)

    assert compacted == "Alpha signal Beta signal needs..."


def test_prepare_memory_content_extracts_summary_chunks_tags_and_checksum() -> None:
    prepared = prepare_memory_content(
        "BTC market signal. " * 80,
        title="Market memo",
        source_url="https://example.com/memo",
        max_summary_chars=80,
        chunk_chars=120,
    )

    assert prepared.title == "Market memo"
    assert len(prepared.summary) <= 83
    assert len(prepared.chunks) > 1
    assert "market" in prepared.tags
    assert prepared.checksum


def test_parse_rss_entries() -> None:
    entries = parse_feed_entries(
        """
        <rss>
          <channel>
            <item>
              <title>One</title>
              <link>https://example.com/one</link>
              <description><![CDATA[<p>Summary</p>]]></description>
              <pubDate>Wed, 06 May 2026 10:00:00 GMT</pubDate>
            </item>
          </channel>
        </rss>
        """
    )

    assert len(entries) == 1
    assert entries[0].title == "One"
    assert entries[0].summary == "Summary"


def test_parse_atom_entries() -> None:
    entries = parse_feed_entries(
        """
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Atom item</title>
            <link href="https://example.com/atom" />
            <summary>Atom summary</summary>
            <updated>2026-05-06T10:00:00Z</updated>
          </entry>
        </feed>
        """
    )

    assert entries[0].title == "Atom item"
    assert entries[0].link == "https://example.com/atom"


def test_add_rss_subscription_deduplicates_urls(tmp_path) -> None:
    add_rss_subscription(str(tmp_path), user_id=123, feed_url="https://example.com/feed.xml")
    path = add_rss_subscription(str(tmp_path), user_id=123, feed_url="https://example.com/feed.xml")

    assert path.read_text(encoding="utf-8").splitlines() == ["https://example.com/feed.xml"]


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/feed.xml",
        "https://localhost/feed.xml",
        "https://postgres/feed.xml",
        "http://127.0.0.1/feed.xml",
        "http://10.0.0.1/feed.xml",
        "http://[::1]/feed.xml",
        "https://user:password@example.com/feed.xml",
    ],
)
def test_validate_public_url_rejects_non_public_targets(url: str) -> None:
    with pytest.raises(ValueError):
        validate_public_url(url)


def test_get_public_url_rejects_private_redirect(monkeypatch) -> None:
    async def fake_resolution(hostname: str, port: int | None) -> None:
        return None

    class FakeClient:
        async def get(self, url: str) -> httpx.Response:
            return httpx.Response(
                302,
                headers={"location": "http://127.0.0.1/admin"},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(knowledge_ingestion, "_validate_public_resolution", fake_resolution)

    with pytest.raises(ValueError):
        asyncio.run(knowledge_ingestion._get_public_url(FakeClient(), "https://example.com/feed"))


def test_format_feed_digests_handles_empty_list() -> None:
    assert format_feed_digests([]) == "RSS-подписок пока нет."
