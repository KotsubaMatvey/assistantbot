from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class AssistantToolDef:
    name: str
    description: str


TOOL_REGISTRY = (
    AssistantToolDef("calc", "safe arithmetic calculator"),
    AssistantToolDef("slug", "normalize text into a slug"),
    AssistantToolDef("now", "show current time in configured timezone"),
)


def list_tools() -> list[AssistantToolDef]:
    return list(TOOL_REGISTRY)


def run_tool(*, name: str, text: str, timezone_name: str = "Europe/Moscow") -> str:
    normalized = name.strip().lower()
    if normalized == "calc":
        return str(_safe_eval(text))
    if normalized == "slug":
        return _slug(text)
    if normalized == "now":
        return datetime.now(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M:%S %Z")
    raise ValueError("unknown tool")


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
