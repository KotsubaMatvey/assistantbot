from __future__ import annotations

import ast
import json
import operator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class AssistantToolDef:
    name: str
    description: str
    skill: str
    risk_level: str = "low"
    input_schema: str = "text"
    requires_approval: bool = False
    enabled: bool = True


@dataclass(frozen=True)
class ToolUsage:
    name: str
    last_used_at: datetime | None = None
    last_error: str = ""


TOOL_REGISTRY = (
    AssistantToolDef(
        name="calc",
        description="safe arithmetic calculator",
        skill="assistant",
        input_schema='{"expression":"number-only arithmetic"}',
    ),
    AssistantToolDef(
        name="slug",
        description="normalize text into a slug",
        skill="memory",
        input_schema='{"text":"string"}',
    ),
    AssistantToolDef(
        name="now",
        description="show current time in configured timezone",
        skill="assistant",
        input_schema='{"timezone":"configured"}',
    ),
)


class ToolUsageStore:
    def __init__(self, vault_path: str) -> None:
        self.path = Path(vault_path).expanduser() / "tools" / "usage.json"

    def record_success(self, name: str, *, now: datetime | None = None) -> None:
        self._update(name, last_used_at=now or datetime.now(UTC), last_error="")

    def record_error(self, name: str, error: str, *, now: datetime | None = None) -> None:
        self._update(name, last_used_at=now or datetime.now(UTC), last_error=error[:300])

    def list_usage(self) -> dict[str, ToolUsage]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return {name: _usage_from_dict(name, item) for name, item in raw.items()}

    def _update(self, name: str, *, last_used_at: datetime, last_error: str) -> None:
        usage = self.list_usage()
        usage[name] = ToolUsage(name=name, last_used_at=last_used_at, last_error=last_error)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {key: _usage_to_dict(value) for key, value in usage.items()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def list_tools() -> list[AssistantToolDef]:
    return list(TOOL_REGISTRY)


def format_tool_registry(tools: list[AssistantToolDef], usage: dict[str, ToolUsage]) -> str:
    lines = ["Tools registry:"]
    for tool in tools:
        state = usage.get(tool.name)
        approval = "approval" if tool.requires_approval else "no approval"
        enabled = "enabled" if tool.enabled else "disabled"
        last_used = state.last_used_at.isoformat() if state and state.last_used_at else "never"
        last_error = state.last_error if state else ""
        lines.append(
            f"- {tool.name} [{tool.skill}, risk:{tool.risk_level}, {approval}, {enabled}]\n"
            f"  schema: {tool.input_schema}\n"
            f"  last_used: {last_used}\n"
            f"  last_error: {last_error or 'none'}\n"
            f"  {tool.description}"
        )
    return "\n".join(lines)


def run_tool(*, name: str, text: str, timezone_name: str = "Europe/Moscow") -> str:
    normalized = name.strip().lower()
    if normalized == "calc":
        return str(_safe_eval(text))
    if normalized == "slug":
        return _slug(text)
    if normalized == "now":
        return datetime.now(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M:%S %Z")
    raise ValueError("unknown tool")


def _usage_to_dict(usage: ToolUsage) -> dict[str, str]:
    return {
        "last_used_at": usage.last_used_at.isoformat() if usage.last_used_at else "",
        "last_error": usage.last_error,
    }


def _usage_from_dict(name: str, raw: dict[str, str]) -> ToolUsage:
    return ToolUsage(
        name=name,
        last_used_at=_parse_datetime(raw.get("last_used_at", "")),
        last_error=raw.get("last_error", ""),
    )


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _slug(text: str) -> str:
    raw_slug = "".join(_slug_char(char) for char in text.lower())
    return "-".join(part for part in raw_slug.split("-") if part)


def _slug_char(char: str) -> str:
    if char.isalnum():
        return char
    return "-"


def _safe_eval(expression: str) -> int | float:
    tree = ast.parse(expression.strip(), mode="eval")
    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> int | float:
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_node(node.operand)
    if isinstance(node, ast.BinOp):
        operator_fn = operators.get(type(node.op))
        if operator_fn is None:
            raise ValueError("operator is not allowed")
        return operator_fn(_eval_node(node.left), _eval_node(node.right))
    raise ValueError("expression is not allowed")
