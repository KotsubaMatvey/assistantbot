from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class BackupResult:
    path: Path
    files_count: int


class SecuritySettings(Protocol):
    obsidian_vault_path: str
    assistant_access_mode: str
    assistant_context_visibility: str
    assistant_group_trigger_policy: str
    admin_telegram_ids: list[int]


def check_vault(vault_path: str) -> CheckResult:
    path = Path(vault_path).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return CheckResult("Obsidian vault", True, str(path))
    except Exception as exc:
        return CheckResult("Obsidian vault", False, str(exc))


def check_memory_index(vault_path: str) -> CheckResult:
    path = Path(vault_path).expanduser() / ".assistantbot" / "memory-index.sqlite3"
    if path.exists():
        return CheckResult("Memory index", True, str(path))
    return CheckResult("Memory index", True, "will be created on first search")


def check_access_control(vault_path: str, mode: str) -> CheckResult:
    if mode == "open":
        return CheckResult("Access control", True, "mode=open")
    security_dir = Path(vault_path).expanduser() / "security"
    return CheckResult("Access control", security_dir.exists(), f"mode={mode}")


def security_audit_checks(*, settings: SecuritySettings, repo_root: str) -> list[CheckResult]:
    return [
        check_pairing_first(settings.assistant_access_mode),
        check_admin_ids(settings.admin_telegram_ids, settings.assistant_access_mode),
        check_context_visibility(settings.assistant_context_visibility),
        check_group_trigger_policy(settings.assistant_group_trigger_policy),
        check_vault_gitignore(repo_root),
        check_secret_files(repo_root),
    ]


def check_pairing_first(mode: str) -> CheckResult:
    if mode == "pairing":
        return CheckResult("DM pairing", True, "mode=pairing")
    if mode == "open":
        return CheckResult("DM pairing", False, "mode=open allows unknown users")
    return CheckResult("DM pairing", True, f"mode={mode}")


def check_admin_ids(admin_ids: list[int], mode: str) -> CheckResult:
    if admin_ids:
        return CheckResult("Admin IDs", True, f"{len(admin_ids)} admin id(s)")
    if mode == "open":
        return CheckResult("Admin IDs", True, "not required while mode=open")
    return CheckResult("Admin IDs", False, "ADMIN_TELEGRAM_IDS is empty")


def check_context_visibility(value: str) -> CheckResult:
    if value == "allowlist":
        return CheckResult("Context visibility", True, "allowlist")
    return CheckResult("Context visibility", False, f"{value}; recommended allowlist")


def check_group_trigger_policy(value: str) -> CheckResult:
    if value == "mention":
        return CheckResult("Group trigger policy", True, "mention")
    return CheckResult("Group trigger policy", False, f"{value}; recommended mention")


def check_vault_gitignore(repo_root: str) -> CheckResult:
    gitignore = Path(repo_root) / ".gitignore"
    if not gitignore.exists():
        return CheckResult("Vault gitignore", False, ".gitignore missing")
    ignored = any(
        line.strip().rstrip("/") == "assistantbotmemory"
        for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()
    )
    if ignored:
        return CheckResult("Vault gitignore", True, "assistantbotmemory ignored")
    return CheckResult("Vault gitignore", False, "assistantbotmemory is not ignored")


def check_secret_files(repo_root: str) -> CheckResult:
    root = Path(repo_root)
    gitignore = root / ".gitignore"
    env_file = root / ".env"
    if not env_file.exists():
        return CheckResult(".env", True, ".env не найден в рабочей папке")
    if not gitignore.exists():
        return CheckResult(".env", False, ".gitignore отсутствует")
    ignored = any(line.strip() == ".env" for line in gitignore.read_text().splitlines())
    if ignored:
        return CheckResult(".env", True, ".env закрыт через .gitignore")
    return CheckResult(".env", False, ".env есть, но не найден в .gitignore")


def check_docker_compose(repo_root: str) -> list[CheckResult]:
    path = Path(repo_root) / "docker-compose.yml"
    if not path.exists():
        return [CheckResult("Docker Compose", False, "docker-compose.yml не найден")]
    text = path.read_text(encoding="utf-8")
    return [
        CheckResult("Docker Compose", True, "docker-compose.yml найден"),
        CheckResult(
            "Docker restart",
            "restart:" in text,
            "найден restart policy" if "restart:" in text else "restart policy не найден",
        ),
        CheckResult(
            "Memory volume",
            "assistantbotmemory" in text,
            "volume памяти найден" if "assistantbotmemory" in text else "volume памяти не найден",
        ),
    ]


def create_backup(
    *,
    repo_root: str,
    vault_path: str,
    backup_dir: str = "backups",
) -> BackupResult:
    root = Path(repo_root)
    vault = Path(vault_path).expanduser()
    destination = root / backup_dir
    destination.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    archive = destination / f"assistantbot-backup-{timestamp}.zip"

    files_count = 0
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in _iter_backup_files(vault):
            zf.write(path, Path("assistantbotmemory") / path.relative_to(vault))
            files_count += 1
        for relative in ("README.md", ".env.example", "docker-compose.yml"):
            path = root / relative
            if path.exists():
                zf.write(path, Path("project") / relative)
                files_count += 1
        zf.writestr(
            "backup-info.txt",
            f"created_at={datetime.now(UTC).isoformat()}\n"
            f"repo_root={root}\n"
            f"vault_path={vault}\n"
            "database_dump=not_included\n",
        )
        files_count += 1
    return BackupResult(path=archive, files_count=files_count)


def format_checks(checks: list[CheckResult]) -> str:
    lines = []
    for check in checks:
        mark = "OK" if check.ok else "FAIL"
        lines.append(f"{mark} {check.name}: {check.detail}")
    return "\n".join(lines)


def repo_root_from_cwd() -> str:
    return os.getcwd()


def _iter_backup_files(vault: Path) -> list[Path]:
    if not vault.exists():
        return []
    return [path for path in vault.rglob("*") if path.is_file()]
