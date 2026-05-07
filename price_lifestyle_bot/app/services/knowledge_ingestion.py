from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

MAX_REDIRECTS = 5


@dataclass(frozen=True)
class PageSummary:
    url: str
    title: str
    summary: str


@dataclass(frozen=True)
class FeedEntry:
    title: str
    link: str
    summary: str
    published: str | None = None


@dataclass(frozen=True)
class FeedDigest:
    feed_url: str
    entries: list[FeedEntry]
    error_message: str | None = None


def validate_public_url(url: str) -> str:
    clean_url = url.strip()
    parsed = urlparse(clean_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.hostname is None:
        raise ValueError("URL должен начинаться с http:// или https://")
    if parsed.username or parsed.password:
        raise ValueError("URL не должен содержать логин или пароль")
    _validate_public_host(parsed.hostname)
    return clean_url


async def fetch_page_summary(url: str) -> PageSummary:
    clean_url = validate_public_url(url)
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
        response = await _get_public_url(client, clean_url)
    return extract_page_summary(response.text, clean_url)


def extract_page_summary(html: str, url: str, *, max_chars: int = 1200) -> PageSummary:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    body = soup.body or soup
    text = " ".join(body.get_text(" ", strip=True).split())
    return PageSummary(url=url, title=title[:200], summary=text[:max_chars])


def format_learned_page_note(page: PageSummary) -> str:
    return "\n".join(
        [
            f"Источник: {page.url}",
            f"Заголовок: {page.title}",
            "",
            page.summary,
        ]
    )


def add_rss_subscription(vault_path: str, *, user_id: int, feed_url: str) -> Path:
    clean_url = validate_public_url(feed_url)
    directory = Path(vault_path).expanduser() / "users" / str(user_id) / "rss"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "subscriptions.txt"
    existing = list_rss_subscriptions(vault_path, user_id=user_id)
    if clean_url not in existing:
        with path.open("a", encoding="utf-8") as file:
            file.write(f"{clean_url}\n")
    return path


def list_rss_subscriptions(vault_path: str, *, user_id: int) -> list[str]:
    path = Path(vault_path).expanduser() / "users" / str(user_id) / "rss" / "subscriptions.txt"
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


async def fetch_feed_digests(feed_urls: list[str], *, limit_per_feed: int = 5) -> list[FeedDigest]:
    digests: list[FeedDigest] = []
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
        for feed_url in feed_urls:
            try:
                response = await _get_public_url(client, validate_public_url(feed_url))
                entries = parse_feed_entries(response.text, limit=limit_per_feed)
                digests.append(FeedDigest(feed_url=feed_url, entries=entries))
            except Exception as exc:
                digests.append(FeedDigest(feed_url=feed_url, entries=[], error_message=str(exc)))
    return digests


def parse_feed_entries(xml_text: str, *, limit: int = 5) -> list[FeedEntry]:
    root = ET.fromstring(xml_text)
    if _local_name(root.tag) == "rss":
        items = [element for element in root.iter() if _local_name(element.tag) == "item"]
    else:
        items = [element for element in root.iter() if _local_name(element.tag) == "entry"]
    return [_entry_from_element(item) for item in items[:limit]]


def format_feed_digests(digests: list[FeedDigest]) -> str:
    if not digests:
        return "RSS-подписок пока нет."

    lines: list[str] = ["RSS digest"]
    for digest in digests:
        lines.append("")
        lines.append(digest.feed_url)
        if digest.error_message:
            lines.append(f"Ошибка: {digest.error_message[:200]}")
            continue
        if not digest.entries:
            lines.append("Новых или читаемых записей не найдено.")
            continue
        for entry in digest.entries:
            link = f" — {entry.link}" if entry.link else ""
            published = f" ({entry.published})" if entry.published else ""
            lines.append(f"- {entry.title}{published}{link}")
    return "\n".join(lines)


def format_digest_memory_note(digests: list[FeedDigest]) -> str:
    return format_feed_digests(digests)


def _entry_from_element(element: ET.Element) -> FeedEntry:
    title = _child_text(element, "title") or "Без заголовка"
    link = _child_text(element, "link") or _child_attr(element, "link", "href") or ""
    summary = (
        _child_text(element, "description")
        or _child_text(element, "summary")
        or _child_text(element, "content")
        or ""
    )
    published = (
        _child_text(element, "pubDate")
        or _child_text(element, "published")
        or _child_text(element, "updated")
    )
    return FeedEntry(
        title=_clean_text(title)[:200],
        link=link.strip(),
        summary=_clean_text(summary)[:500],
        published=published,
    )


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if _local_name(child.tag) == name and child.text:
            return child.text.strip()
    return None


def _child_attr(element: ET.Element, name: str, attr: str) -> str | None:
    for child in element:
        if _local_name(child.tag) == name and child.get(attr):
            return child.get(attr)
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(text, "html.parser").get_text(" ", strip=True))


def _validate_public_host(hostname: str) -> None:
    host = hostname.rstrip(".").lower()
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if host == "localhost" or host.endswith(".localhost") or "." not in host:
            raise ValueError("URL должен указывать на публичный домен") from None
        return
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError("URL не должен указывать на приватный или локальный адрес")


async def _validate_public_resolution(hostname: str, port: int | None) -> None:
    def resolve() -> list[str]:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        return [str(address[-1][0]) for address in addresses]

    for address in await asyncio.to_thread(resolve):
        _validate_public_host(address)


async def _get_public_url(client: httpx.AsyncClient, url: str) -> httpx.Response:
    current_url = validate_public_url(url)
    for _ in range(MAX_REDIRECTS + 1):
        parsed = urlparse(current_url)
        if parsed.hostname is None:
            raise ValueError("URL должен содержать хост")
        await _validate_public_resolution(parsed.hostname, parsed.port)
        response = await client.get(current_url)
        if not response.is_redirect:
            response.raise_for_status()
            return response
        location = response.headers.get("location")
        if not location:
            response.raise_for_status()
            return response
        current_url = validate_public_url(urljoin(str(response.url), location))
    raise ValueError("Слишком много перенаправлений")
