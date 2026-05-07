from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlparse

from app.services.obsidian_memory import MemorySource


@dataclass(frozen=True)
class SourceTrust:
    domain: str
    count: int
    trust_level: str


def build_source_trust(sources: list[MemorySource]) -> list[SourceTrust]:
    counts: Counter[str] = Counter()
    for source in sources:
        if not source.source_url:
            continue
        domain = urlparse(source.source_url).netloc.lower()
        if domain:
            counts[domain] += 1
    return [
        SourceTrust(domain=domain, count=count, trust_level=_trust_level(count))
        for domain, count in counts.most_common()
    ]


def format_source_trust(items: list[SourceTrust]) -> str:
    if not items:
        return "Source trust: web sources not found."
    lines = ["Source trust:"]
    lines.extend(f"- {item.domain}: {item.count}, {item.trust_level}" for item in items)
    return "\n".join(lines)


def _trust_level(count: int) -> str:
    if count >= 5:
        return "frequent"
    if count >= 2:
        return "known"
    return "new"
