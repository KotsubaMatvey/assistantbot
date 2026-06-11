from __future__ import annotations

import json

import httpx
import pytest
from app.config import Settings
from app.services import llm_client
from app.services.llm_client import (
    LLMProviderPool,
    LLMProviderSpec,
    answer_freeform_with_llm,
    answer_question_with_llm,
    check_llm_providers,
    configured_llm_provider_specs,
    format_llm_provider_checks,
    llm_provider_status_lines,
    reset_llm_cooldowns,
)
from app.services.obsidian_memory import ObsidianMemory


def test_configured_llm_provider_specs_reads_json_and_env(monkeypatch) -> None:
    monkeypatch.setenv("TEST_LLM_KEY", "secret")
    settings = Settings(
        llm_provider_order=["custom"],
        llm_provider_specs_json=(
            '[{"name":"custom","base_url":"https://example.com/v1",'
            '"model":"test-model","api_key_env":"TEST_LLM_KEY",'
            '"headers":{"X-Test":"1"}}]'
        ),
    )

    specs = configured_llm_provider_specs(settings)

    assert specs[0].name == "custom"
    assert specs[0].api_key == "secret"
    assert specs[0].headers["X-Test"] == "1"


def test_configured_llm_provider_specs_uses_common_free_cloud_presets() -> None:
    settings = Settings(
        llm_provider_order=["openrouter", "groq"],
        llm_groq_api_key="groq-key",
        llm_cerebras_api_key="",
        llm_openrouter_api_key="openrouter-key",
        llm_openrouter_site_url="https://example.com",
    )

    specs = configured_llm_provider_specs(settings)

    assert [spec.name for spec in specs] == ["openrouter", "groq"]
    assert specs[0].model == "openrouter/free"
    assert specs[0].headers["HTTP-Referer"] == "https://example.com"


def test_configured_llm_provider_specs_accepts_model_fallback_list() -> None:
    settings = Settings(
        llm_provider_order=["groq"],
        llm_groq_api_key="groq-key",
        llm_groq_model="first-model,second-model",
        llm_cerebras_api_key="",
        llm_openrouter_api_key="",
    )

    specs = configured_llm_provider_specs(settings)

    assert [(spec.name, spec.model) for spec in specs] == [
        ("groq", "first-model"),
        ("groq", "second-model"),
    ]


def test_llm_provider_status_does_not_expose_keys() -> None:
    settings = Settings(llm_enabled=True, llm_groq_api_key="secret")

    text = "\n".join(llm_provider_status_lines(settings))

    assert "LLM status" in text
    assert "groq" in text
    assert "secret" not in text


@pytest.mark.asyncio
async def test_provider_pool_falls_back_after_rate_limit() -> None:
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        if request.url.host == "limited.example":
            return httpx.Response(429, headers={"retry-after": "2"}, text="daily limit")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "fallback answer"}}]},
        )

    pool = LLMProviderPool(
        [
            LLMProviderSpec(
                name="limited-provider",
                base_url="https://limited.example/v1",
                model="first",
                api_key="key",
            ),
            LLMProviderSpec(
                name="fallback-provider",
                base_url="https://fallback.example/v1",
                model="second",
                api_key="key",
            ),
        ],
        transport=httpx.MockTransport(handler),
    )

    completion = await pool.complete([{"role": "user", "content": "hello"}])

    assert completion is not None
    assert completion.provider == "fallback-provider"
    assert completion.content == "fallback answer"
    assert hosts == ["limited.example", "fallback.example"]


@pytest.mark.asyncio
async def test_provider_cooldown_persists_to_file(tmp_path) -> None:
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        if request.url.host == "limited.example":
            return httpx.Response(429, headers={"retry-after": "3600"}, text="daily limit")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "fallback answer"}}]},
        )

    providers = [
        LLMProviderSpec(
            name="limited-provider",
            base_url="https://limited.example/v1",
            model="first",
            api_key="key",
        ),
        LLMProviderSpec(
            name="fallback-provider",
            base_url="https://fallback.example/v1",
            model="second",
            api_key="key",
        ),
    ]
    cooldown_path = tmp_path / "cooldowns.json"
    first_pool = LLMProviderPool(
        providers,
        cooldown_path=cooldown_path,
        transport=httpx.MockTransport(handler),
    )
    second_pool = LLMProviderPool(
        providers,
        cooldown_path=cooldown_path,
        transport=httpx.MockTransport(handler),
    )

    assert await first_pool.complete([{"role": "user", "content": "hello"}]) is not None
    assert await second_pool.complete([{"role": "user", "content": "hello"}]) is not None

    assert hosts == ["limited.example", "fallback.example", "fallback.example"]


def test_reset_llm_cooldowns_removes_persisted_entries(tmp_path) -> None:
    settings = Settings(obsidian_vault_path=str(tmp_path))
    cooldown_path = tmp_path / ".assistantbot" / "llm-cooldowns.json"
    cooldown_path.parent.mkdir()
    cooldown_path.write_text(
        '{"groq:model-a":"2099-01-01T00:00:00+00:00","openrouter:model-b":"2099-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )

    removed = reset_llm_cooldowns(settings, provider_name="groq")

    assert removed == 1
    assert "groq:model-a" not in cooldown_path.read_text(encoding="utf-8")
    assert "openrouter:model-b" in cooldown_path.read_text(encoding="utf-8")


def test_memory_context_redaction(tmp_path) -> None:
    path = tmp_path / "note.md"
    path.write_text("email a@example.com phone +7 999 123-45-67 paid 1500 руб", encoding="utf-8")
    result = llm_client.MemorySearchResult(
        path=path,
        score=1,
        snippet="email a@example.com phone +7 999 123-45-67 paid 1500 руб",
    )
    settings = Settings(llm_cloud_context_allowed=True, llm_context_mode="redacted")

    messages = llm_client._memory_question_messages("что?", [result], settings)
    content = messages[1]["content"]

    assert "a@example.com" not in content
    assert "+7 999" not in content
    assert "1500 руб" not in content
    assert "[email]" in content


@pytest.mark.asyncio
async def test_check_llm_providers_reports_each_provider() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "bad.example":
            return httpx.Response(429, text="daily limit")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    settings = Settings(
        llm_provider_order=["bad", "good"],
        llm_provider_specs_json=(
            '[{"name":"bad","base_url":"https://bad.example/v1",'
            '"model":"bad-model","api_key":"bad-key"},'
            '{"name":"good","base_url":"https://good.example/v1",'
            '"model":"good-model","api_key":"good-key"}]'
        ),
    )

    checks = await check_llm_providers(
        settings,
        transport=httpx.MockTransport(handler),
    )
    text = format_llm_provider_checks(checks)

    assert [check.ok for check in checks] == [False, True]
    assert "FAIL bad" in text
    assert "OK good" in text
    assert "bad-key" not in text


@pytest.mark.asyncio
async def test_freeform_answer_sends_history_and_returns_plain_content(tmp_path) -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "свежий ответ"}}]},
        )

    settings = Settings(
        llm_enabled=True,
        obsidian_vault_path=str(tmp_path),
        llm_provider_specs_json=(
            '[{"name":"custom","base_url":"https://example.com/v1",'
            '"model":"test-model","api_key":"secret"}]'
        ),
    )

    answer = await answer_freeform_with_llm(
        text="Продолжи мысль",
        settings=settings,
        history=[
            {"role": "user", "content": "Первый вопрос"},
            {"role": "assistant", "content": "Первый ответ"},
        ],
        transport=httpx.MockTransport(handler),
    )

    assert answer == "свежий ответ"
    messages = bodies[0]["messages"]
    assert messages[0]["role"] == "system"
    assert "second brain" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "Первый вопрос"}
    assert messages[2] == {"role": "assistant", "content": "Первый ответ"}
    assert messages[3] == {"role": "user", "content": "Продолжи мысль"}


@pytest.mark.asyncio
async def test_memory_llm_answer_is_blocked_without_cloud_context_opt_in(tmp_path) -> None:
    memory = ObsidianMemory(str(tmp_path))
    memory.remember_user_note(user_id=123, text="private context about alpha")
    settings = Settings(
        llm_enabled=True,
        llm_cloud_context_allowed=False,
        llm_provider_specs_json=(
            '[{"name":"custom","base_url":"https://example.com/v1",'
            '"model":"test-model","api_key":"secret"}]'
        ),
    )

    answer = await answer_question_with_llm(
        memory=memory,
        user_id=123,
        question="alpha",
        settings=settings,
    )

    assert answer is None
