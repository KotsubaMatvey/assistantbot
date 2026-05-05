from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class BackupResult:
    path: Path
    files_count: int


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
