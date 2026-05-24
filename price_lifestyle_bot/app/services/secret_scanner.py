from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SECRET_PATTERNS = (
    ("telegram_bot_token", re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    (
        "generic_api_key",
        re.compile(r"(?i)\b(api[_-]?key|token|secret)\s*=\s*['\"][^'\"]{16,}['\"]"),
    ),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)


@dataclass(frozen=True)
class SecretFinding:
    path: Path
    line_no: int
    kind: str
    preview: str


def scan_for_secrets(*roots: str, max_file_size: int = 500_000) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for root_text in roots:
        root = Path(root_text).expanduser()
        for path in _iter_scan_files(root, max_file_size=max_file_size):
            findings.extend(_scan_file(path))
    return findings


def format_secret_findings(findings: list[SecretFinding], *, limit: int = 20) -> str:
    if not findings:
        return "Secret scan: findings not found."
    lines = ["Secret scan findings:"]
    for finding in findings[:limit]:
        lines.append(f"- {finding.kind} {finding.path}:{finding.line_no} {finding.preview}")
    if len(findings) > limit:
        lines.append(f"...and {len(findings) - limit} more")
    return "\n".join(lines)


def _iter_scan_files(root: Path, *, max_file_size: int) -> list[Path]:
    if root.is_file():
        return [root] if _can_scan(root, max_file_size=max_file_size) else []
    if not root.exists():
        return []
    ignored_parts = {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
    }
    return [
        path
        for path in root.rglob("*")
        if path.is_file()
        and not ignored_parts.intersection(path.parts)
        and _can_scan(path, max_file_size=max_file_size)
    ]


def _can_scan(path: Path, *, max_file_size: int) -> bool:
    try:
        return path.stat().st_size <= max_file_size
    except OSError:
        return False


def _scan_file(path: Path) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    for line_no, line in enumerate(lines, start=1):
        for kind, pattern in SECRET_PATTERNS:
            match = pattern.search(line)
            if match is None:
                continue
            findings.append(
                SecretFinding(
                    path=path,
                    line_no=line_no,
                    kind=kind,
                    preview=_redact(match.group(0)),
                )
            )
    return findings


def _redact(value: str) -> str:
    clean = value.strip()
    if len(clean) <= 8:
        return "***"
    return f"{clean[:4]}...{clean[-4:]}"
