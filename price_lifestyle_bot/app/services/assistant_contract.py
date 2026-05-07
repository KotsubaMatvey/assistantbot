from __future__ import annotations

from dataclasses import dataclass, field

from app.services.obsidian_memory import MemorySearchResult, ObsidianMemory


@dataclass(frozen=True)
class AssistantCapability:
    name: str
    enabled: bool
    description: str


@dataclass(frozen=True)
class AssistantContextItem:
    title: str
    snippet: str
    citation: str
    source_type: str
    space: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AssistantThreadSnapshot:
    user_id: int
    active_space: str
    query: str
    context: list[AssistantContextItem]
    capabilities: list[AssistantCapability]


def assistant_capabilities() -> list[AssistantCapability]:
    return [
        AssistantCapability("markdown_memory", True, "Local markdown-backed memory"),
        AssistantCapability("sqlite_fts_search", True, "SQLite FTS5 full-text search"),
        AssistantCapability("spaces", True, "Workspace/notebook style memory spaces"),
        AssistantCapability("citations", True, "Search results include local citations"),
        AssistantCapability("tool_approvals", True, "Dangerous actions require approval codes"),
        AssistantCapability(
            "pairing_allowlist",
            True,
            "Optional pairing and allowlist access control",
        ),
        AssistantCapability("llm_answers", False, "LLM layer is intentionally not connected yet"),
        AssistantCapability(
            "vector_search",
            False,
            "Embeddings are reserved for the LLM/RAG phase",
        ),
    ]


def build_thread_snapshot(
    *,
    memory: ObsidianMemory,
    user_id: int,
    query: str,
    limit: int = 5,
) -> AssistantThreadSnapshot:
    results = memory.search_user_notes(user_id=user_id, query=query, limit=limit)
    return AssistantThreadSnapshot(
        user_id=user_id,
        active_space=memory.get_active_space(user_id),
        query=query,
        context=[_context_item(result) for result in results],
        capabilities=assistant_capabilities(),
    )


def _context_item(result: MemorySearchResult) -> AssistantContextItem:
    return AssistantContextItem(
        title=result.title or result.path.name,
        snippet=result.snippet,
        citation=result.citation,
        source_type=result.source_type,
        space=result.space,
        tags=result.tags,
    )
