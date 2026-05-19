from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings
from app.logging_config import get_logger
from app.services.obsidian_memory import MemorySearchResult, ObsidianMemory

logger = get_logger(__name__)

QUOTA_ERROR_STATUSES = {402, 403, 429}
_provider_cooldowns: dict[str, datetime] = {}
LLM_CONTEXT_MODES = {"none", "snippets", "redacted", "full"}
MAX_FULL_CONTEXT_CHARS = 1200


@dataclass(frozen=True)
class LLMProviderSpec:
    name: str
    base_url: str
    model: str
    api_key: str = ""
    path: str = "chat/completions"
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def url(self) -> str:
        return "/".join([self.base_url.rstrip("/"), self.path.strip("/")])

    @property
    def cooldown_key(self) -> str:
        return f"{self.name}:{self.model}"


@dataclass(frozen=True)
class LLMCompletion:
    provider: str
    model: str
    content: str


@dataclass(frozen=True)
class LLMProviderCheck:
    provider: str
    model: str
    ok: bool
    detail: str


class LLMProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        quota_like: bool = False,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.quota_like = quota_like


class LLMProviderPool:
    def __init__(
        self,
        providers: list[LLMProviderSpec],
        *,
        timeout_seconds: float = 30.0,
        max_output_tokens: int = 700,
        temperature: float = 0.2,
        daily_limit_cooldown_hours: int = 24,
        cooldown_path: Path | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.providers = providers
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.daily_limit_cooldown_hours = daily_limit_cooldown_hours
        self.cooldown_path = cooldown_path
        self.transport = transport

    async def complete(self, messages: list[dict[str, str]]) -> LLMCompletion | None:
        errors: list[str] = []
        for provider in self.providers:
            if _is_in_cooldown(provider.cooldown_key, self.cooldown_path):
                continue
            try:
                content = await self._complete_with_provider(provider, messages)
            except LLMProviderError as exc:
                errors.append(f"{provider.name}: {exc}")
                if exc.quota_like:
                    _cooldown_provider(
                        provider.cooldown_key,
                        seconds=exc.retry_after_seconds
                        or self.daily_limit_cooldown_hours * 60 * 60,
                        path=self.cooldown_path,
                    )
                continue
            except Exception as exc:
                errors.append(f"{provider.name}: {exc}")
                continue
            if content:
                return LLMCompletion(
                    provider=provider.name,
                    model=provider.model,
                    content=content,
                )
        if errors:
            logger.warning("llm_provider_pool_exhausted", errors=errors[:5])
        return None

    async def _complete_with_provider(
        self,
        provider: LLMProviderSpec,
        messages: list[dict[str, str]],
    ) -> str:
        headers = {"Content-Type": "application/json", **provider.headers}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        body = {
            "model": provider.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
            "stream": False,
        }
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.post(provider.url, headers=headers, json=body)
        if response.status_code in QUOTA_ERROR_STATUSES:
            retry_after = _retry_after_seconds(response)
            raise LLMProviderError(
                _response_error_message(response),
                retry_after_seconds=retry_after,
                quota_like=True,
            )
        if response.status_code >= 400:
            raise LLMProviderError(_response_error_message(response))
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("unexpected response shape") from exc
        if content is None:
            raise LLMProviderError("empty response content")
        text = str(content).strip()
        if not text:
            raise LLMProviderError("empty response content")
        return text


def configured_llm_provider_specs(settings: Settings) -> list[LLMProviderSpec]:
    if settings.llm_provider_specs_json.strip():
        return _ordered_specs(
            [_spec_from_mapping(item) for item in _json_specs(settings.llm_provider_specs_json)],
            settings.llm_provider_order,
        )
    specs = [
        *(
            _model_specs(
                name="groq",
                base_url="https://api.groq.com/openai/v1",
                models=settings.llm_groq_model,
                api_key=settings.llm_groq_api_key,
            )
            if settings.llm_groq_api_key
            else []
        ),
        *(
            _model_specs(
                name="cerebras",
                base_url="https://api.cerebras.ai/v1",
                models=settings.llm_cerebras_model,
                api_key=settings.llm_cerebras_api_key,
            )
            if settings.llm_cerebras_api_key
            else []
        ),
        *(
            _model_specs(
                name="openrouter",
                base_url="https://openrouter.ai/api/v1",
                models=settings.llm_openrouter_model,
                api_key=settings.llm_openrouter_api_key,
                headers=_openrouter_headers(settings),
            )
            if settings.llm_openrouter_api_key
            else []
        ),
        *(
            _model_specs(
                name="mistral",
                base_url="https://api.mistral.ai/v1",
                models=settings.llm_mistral_model,
                api_key=settings.llm_mistral_api_key,
            )
            if settings.llm_mistral_api_key
            else []
        ),
        *(
            _model_specs(
                name="github_models",
                base_url="https://models.github.ai/inference",
                models=settings.llm_github_models_model,
                api_key=settings.llm_github_models_token,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2026-03-10",
                },
            )
            if settings.llm_github_models_token
            else []
        ),
        *(
            _model_specs(
                name="zai",
                base_url="https://open.bigmodel.cn/api/paas/v4",
                models=settings.llm_zai_model,
                api_key=settings.llm_zai_api_key,
            )
            if settings.llm_zai_api_key
            else []
        ),
        *(
            _model_specs(
                name="nvidia",
                base_url="https://integrate.api.nvidia.com/v1",
                models=settings.llm_nvidia_model,
                api_key=settings.llm_nvidia_api_key,
            )
            if settings.llm_nvidia_api_key
            else []
        ),
        *(
            _model_specs(
                name="llm7",
                base_url="https://api.llm7.io/v1",
                models=settings.llm_llm7_model,
                api_key=settings.llm_llm7_api_key,
            )
            if settings.llm_llm7_api_key
            else []
        ),
        *(
            _model_specs(
                name="ovh",
                base_url="https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
                models=settings.llm_ovh_model,
                api_key=settings.llm_ovh_api_key,
            )
            if settings.llm_ovh_api_key
            else []
        ),
        *(
            _model_specs(
                name="siliconflow",
                base_url="https://api.siliconflow.cn/v1",
                models=settings.llm_siliconflow_model,
                api_key=settings.llm_siliconflow_api_key,
            )
            if settings.llm_siliconflow_api_key
            else []
        ),
    ]
    return _ordered_specs(specs, settings.llm_provider_order)


def llm_provider_status_lines(settings: Settings) -> list[str]:
    providers = configured_llm_provider_specs(settings)
    cooldowns = _load_cooldowns(_cooldown_path(settings))
    lines = [
        "LLM status",
        f"Enabled: {'yes' if settings.llm_enabled else 'no'}",
        f"Cloud memory context: {'allowed' if settings.llm_cloud_context_allowed else 'blocked'}",
        f"Context mode: {_effective_context_mode(settings)}",
        f"Configured providers: {len(providers)}",
    ]
    if not providers:
        lines.append("No provider API keys configured.")
        return lines
    for provider in providers:
        cooldown_until = cooldowns.get(provider.cooldown_key)
        if cooldown_until and cooldown_until > datetime.now(UTC):
            cooldown = f"cooldown until {cooldown_until:%Y-%m-%d %H:%M:%S UTC}"
        else:
            cooldown = "ready"
        lines.append(f"- {provider.name}: {provider.model} ({cooldown})")
    return lines


def llm_model_lines(settings: Settings) -> list[str]:
    providers = configured_llm_provider_specs(settings)
    if not providers:
        return ["LLM models", "No provider API keys configured."]
    lines = ["LLM models"]
    for provider in providers:
        lines.append(f"- {provider.name}: {provider.model}")
    return lines


def reset_llm_cooldowns(settings: Settings, *, provider_name: str | None = None) -> int:
    path = _cooldown_path(settings)
    cooldowns = _load_cooldowns(path)
    if provider_name:
        normalized = provider_name.strip().lower()
        keys = [key for key in cooldowns if key.split(":", 1)[0].lower() == normalized]
    else:
        keys = list(cooldowns)
    for key in keys:
        cooldowns.pop(key, None)
        _provider_cooldowns.pop(key, None)
    _save_cooldowns(path, cooldowns)
    return len(keys)


async def check_llm_providers(
    settings: Settings,
    *,
    prompt: str = "Ответь одним словом: ok",
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[LLMProviderCheck]:
    providers = configured_llm_provider_specs(settings)
    checks: list[LLMProviderCheck] = []
    for provider in providers:
        pool = LLMProviderPool(
            [provider],
            timeout_seconds=settings.llm_timeout_seconds,
            max_output_tokens=max(120, min(settings.llm_max_output_tokens, 200)),
            temperature=0,
            daily_limit_cooldown_hours=settings.llm_daily_limit_cooldown_hours,
            cooldown_path=_cooldown_path(settings),
            transport=transport,
        )
        completion = await pool.complete(
            [
                {
                    "role": "system",
                    "content": "Ты diagnostic healthcheck. Ответь кратко.",
                },
                {"role": "user", "content": prompt},
            ]
        )
        if completion is None:
            checks.append(
                LLMProviderCheck(
                    provider=provider.name,
                    model=provider.model,
                    ok=False,
                    detail="failed or rate-limited",
                )
            )
            continue
        checks.append(
            LLMProviderCheck(
                provider=provider.name,
                model=provider.model,
                ok=True,
                detail=completion.content[:120],
            )
        )
    return checks


def format_llm_provider_checks(checks: list[LLMProviderCheck]) -> str:
    if not checks:
        return "LLM test\nNo provider API keys configured."
    lines = ["LLM test"]
    for check in checks:
        mark = "OK" if check.ok else "FAIL"
        lines.append(f"- {mark} {check.provider}: {check.model} — {check.detail}")
    return "\n".join(lines)


async def answer_question_with_llm(
    *,
    memory: ObsidianMemory,
    user_id: int,
    question: str,
    settings: Settings,
) -> str | None:
    if not settings.llm_enabled:
        return None
    if not settings.llm_cloud_context_allowed:
        return None
    if _effective_context_mode(settings) == "none":
        return None
    providers = configured_llm_provider_specs(settings)
    if not providers:
        return None
    results = memory.search_user_notes(
        user_id=user_id,
        query=question,
        limit=settings.llm_max_context_notes,
    )
    if not results:
        return None
    pool = LLMProviderPool(
        providers,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
        temperature=settings.llm_temperature,
        daily_limit_cooldown_hours=settings.llm_daily_limit_cooldown_hours,
        cooldown_path=_cooldown_path(settings),
    )
    completion = await pool.complete(_memory_question_messages(question, results, settings))
    if completion is None:
        return None
    return f"{completion.content}\n\nLLM: {completion.provider} / {completion.model}"


async def answer_freeform_with_llm(
    *,
    text: str,
    settings: Settings,
) -> str | None:
    if not settings.llm_enabled:
        return None
    providers = configured_llm_provider_specs(settings)
    if not providers:
        return None
    pool = LLMProviderPool(
        providers,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
        temperature=settings.llm_temperature,
        daily_limit_cooldown_hours=settings.llm_daily_limit_cooldown_hours,
        cooldown_path=_cooldown_path(settings),
    )
    completion = await pool.complete(
        [
            {
                "role": "system",
                "content": (
                    "Ты краткий Telegram assistant. Отвечай по-русски, без выполнения "
                    "локальных действий и без выдумывания доступа к памяти."
                ),
            },
            {"role": "user", "content": text},
        ]
    )
    if completion is None:
        return None
    return f"{completion.content}\n\nLLM: {completion.provider} / {completion.model}"


def _memory_question_messages(
    question: str,
    results: list[MemorySearchResult],
    settings: Settings,
) -> list[dict[str, str]]:
    context_lines = []
    context_mode = _effective_context_mode(settings)
    for index, result in enumerate(results, start=1):
        context_text = _context_text(result, context_mode)
        context_lines.append(
            f"[{index}] {result.title or result.path.name}\n"
            f"Context: {context_text}\n"
            f"Citation: {result.citation}"
        )
    return [
        {
            "role": "system",
            "content": (
                "Ты отвечаешь по локальной памяти пользователя. Используй только контекст ниже. "
                "Если ответа в контексте нет, скажи, что в памяти нет достаточных данных. "
                "Отвечай по-русски и указывай номера источников вида [1]."
            ),
        },
        {
            "role": "user",
            "content": "Вопрос:\n" + question + "\n\nКонтекст:\n" + "\n\n".join(context_lines),
        },
    ]


def _json_specs(raw: str) -> list[dict[str, Any]]:
    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError("LLM_PROVIDER_SPECS_JSON must be a JSON list")
    specs = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each LLM provider spec must be an object")
        specs.append(item)
    return specs


def _spec_from_mapping(item: dict[str, Any]) -> LLMProviderSpec:
    api_key = str(item.get("api_key") or "")
    api_key_env = str(item.get("api_key_env") or "")
    if not api_key and api_key_env:
        api_key = os.getenv(api_key_env, "")
    headers = item.get("headers") or {}
    if not isinstance(headers, dict):
        raise ValueError("LLM provider headers must be an object")
    return LLMProviderSpec(
        name=str(item["name"]),
        base_url=str(item["base_url"]),
        model=str(item["model"]),
        api_key=api_key,
        path=str(item.get("path") or "chat/completions"),
        headers={str(key): str(value) for key, value in headers.items()},
    )


def _model_specs(
    *,
    name: str,
    base_url: str,
    models: str,
    api_key: str,
    headers: dict[str, str] | None = None,
) -> list[LLMProviderSpec]:
    return [
        LLMProviderSpec(
            name=name,
            base_url=base_url,
            model=model,
            api_key=api_key,
            headers=headers or {},
        )
        for model in _parse_model_names(models)
    ]


def _parse_model_names(value: str) -> list[str]:
    text = value.strip()
    if not text:
        return []
    if text.startswith("["):
        raw = json.loads(text)
        if not isinstance(raw, list):
            raise ValueError("LLM model list must be a JSON list")
        return [str(item).strip() for item in raw if str(item).strip()]
    return [part.strip() for part in text.split(",") if part.strip()]


def _ordered_specs(
    specs: list[LLMProviderSpec],
    provider_order: list[str],
) -> list[LLMProviderSpec]:
    order = {name: index for index, name in enumerate(provider_order)}
    return sorted(specs, key=lambda spec: (order.get(spec.name, len(order)), spec.name))


def _openrouter_headers(settings: Settings) -> dict[str, str]:
    headers = {"X-Title": settings.llm_openrouter_app_name}
    if settings.llm_openrouter_site_url:
        headers["HTTP-Referer"] = settings.llm_openrouter_site_url
    return headers


def _retry_after_seconds(response: httpx.Response) -> int | None:
    for header in (
        "retry-after",
        "x-ratelimit-reset-requests",
        "x-ratelimit-reset-requests-day",
    ):
        raw = response.headers.get(header)
        if not raw:
            continue
        parsed = _parse_seconds(raw)
        if parsed is not None:
            return parsed
    return None


def _parse_seconds(value: str) -> int | None:
    clean = value.strip().lower()
    try:
        return max(1, int(float(clean)))
    except ValueError:
        pass
    minute_marker = clean.find("m")
    if minute_marker > 0 and clean.endswith("s"):
        minutes = clean[:minute_marker]
        seconds = clean[minute_marker + 1 : -1]
        try:
            return max(1, int(float(minutes) * 60 + float(seconds)))
        except ValueError:
            return None
    if clean.endswith("s"):
        try:
            return max(1, int(float(clean[:-1])))
        except ValueError:
            return None
    if clean.endswith("m"):
        try:
            return max(1, int(float(clean[:-1]) * 60))
        except ValueError:
            return None
    return None


def _response_error_message(response: httpx.Response) -> str:
    text = response.text[:500]
    return f"HTTP {response.status_code}: {text}"


def _cooldown_provider(name: str, *, seconds: int, path: Path | None = None) -> None:
    cooldowns = _load_cooldowns(path)
    cooldowns[name] = datetime.now(UTC) + timedelta(seconds=seconds)
    _provider_cooldowns[name] = cooldowns[name]
    _save_cooldowns(path, cooldowns)


def _is_in_cooldown(name: str, path: Path | None = None) -> bool:
    cooldowns = _load_cooldowns(path)
    until = cooldowns.get(name)
    if until is None:
        return False
    if until <= datetime.now(UTC):
        cooldowns.pop(name, None)
        _save_cooldowns(path, cooldowns)
        return False
    return True


def _cooldown_path(settings: Settings) -> Path:
    return Path(settings.obsidian_vault_path).expanduser() / ".assistantbot" / "llm-cooldowns.json"


def _load_cooldowns(path: Path | None) -> dict[str, datetime]:
    if path is None:
        return dict(_provider_cooldowns)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    cooldowns: dict[str, datetime] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        cooldowns[key] = parsed.astimezone(UTC)
    _provider_cooldowns.update(cooldowns)
    return cooldowns


def _save_cooldowns(path: Path | None, cooldowns: dict[str, datetime]) -> None:
    if path is None:
        _provider_cooldowns.clear()
        _provider_cooldowns.update(cooldowns)
        return
    active = {
        key: value.astimezone(UTC).isoformat()
        for key, value in cooldowns.items()
        if value > datetime.now(UTC)
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(active, ensure_ascii=False, indent=2), encoding="utf-8")
    _provider_cooldowns.clear()
    _provider_cooldowns.update(
        {key: datetime.fromisoformat(value) for key, value in active.items()}
    )


def _effective_context_mode(settings: Settings) -> str:
    if not settings.llm_cloud_context_allowed:
        return "none"
    mode = settings.llm_context_mode.strip().lower()
    return mode if mode in LLM_CONTEXT_MODES else "snippets"


def _context_text(result: MemorySearchResult, mode: str) -> str:
    if mode == "full":
        return _read_note_body(result.path)[:MAX_FULL_CONTEXT_CHARS]
    if mode == "redacted":
        return _redact_context(result.snippet)
    return result.snippet


def _read_note_body(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if not text.startswith("---"):
        return " ".join(text.split())
    parts = text.split("---", 2)
    if len(parts) < 3:
        return " ".join(text.split())
    return " ".join(parts[2].split())


def _redact_context(text: str) -> str:
    redacted = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "[email]", text)
    redacted = re.sub(r"\+?\d[\d\s().-]{7,}\d", "[phone]", redacted)
    redacted = re.sub(r"\b(?:sk|ghp|github_pat|glpat)-[A-Za-z0-9_\-]{12,}\b", "[token]", redacted)
    redacted = re.sub(
        r"\b\d+(?:[.,]\d+)?\s*(?:₽|руб|rub|usd|eur|\$|€)\b",
        "[amount]",
        redacted,
        flags=re.I,
    )
    redacted = re.sub(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", "[card]", redacted)
    return redacted
