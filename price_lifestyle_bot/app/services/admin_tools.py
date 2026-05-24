from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy.engine import make_url


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class BackupResult:
    path: Path
    files_count: int


@dataclass(frozen=True)
class RestoreResult:
    archive_path: Path
    vault_files: int
    database_included: bool
    previous_vault_path: Path | None = None


class SecuritySettings(Protocol):
    obsidian_vault_path: str
    assistant_access_mode: str
    assistant_context_visibility: str
    assistant_group_trigger_policy: str
    admin_telegram_ids: list[int]
    mini_app_dev_auth_enabled: bool


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
        check_mini_app_dev_auth(settings.mini_app_dev_auth_enabled),
        check_vault_gitignore(repo_root),
        check_backup_gitignore(repo_root),
        check_secret_files(repo_root),
    ]


def check_pairing_first(mode: str) -> CheckResult:
    if mode == "pairing":
        return CheckResult("DM pairing", True, "mode=pairing")
    if mode == "admin_only":
        return CheckResult("DM pairing", True, "mode=admin_only; owner access only")
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


def check_mini_app_dev_auth(enabled: bool) -> CheckResult:
    if enabled:
        return CheckResult(
            "Mini App dev auth",
            False,
            "enabled; disable before deployment",
        )
    return CheckResult("Mini App dev auth", True, "disabled")


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


def check_backup_gitignore(repo_root: str) -> CheckResult:
    gitignore = Path(repo_root) / ".gitignore"
    if not gitignore.exists():
        return CheckResult("Backup gitignore", False, ".gitignore missing")
    ignored = any(
        line.strip().rstrip("/") == "backups"
        for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()
    )
    if ignored:
        return CheckResult("Backup gitignore", True, "backups ignored")
    return CheckResult("Backup gitignore", False, "backups is not ignored")


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
    database_dump: bytes | None = None,
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
        if database_dump is not None:
            zf.writestr("database/postgres.dump", database_dump)
            files_count += 1
        zf.writestr(
            "backup-info.txt",
            f"created_at={datetime.now(UTC).isoformat()}\n"
            f"repo_root={root}\n"
            f"vault_path={vault}\n"
            f"database_dump={'included' if database_dump is not None else 'not_included'}\n",
        )
        files_count += 1
    return BackupResult(path=archive, files_count=files_count)


def create_postgres_dump(database_url: str) -> bytes:
    command, environment = _postgres_command("pg_dump", database_url)
    try:
        result = subprocess.run(
            [*command, "--format=custom", "--no-owner", "--no-privileges"],
            check=True,
            capture_output=True,
            env=environment,
        )
    except FileNotFoundError:
        result = subprocess.run(
            [
                *_docker_postgres_command("pg_dump", database_url),
                "--format=custom",
                "--no-owner",
                "--no-privileges",
            ],
            check=True,
            capture_output=True,
        )
    return result.stdout


def restore_postgres_dump(database_url: str, dump_path: Path) -> None:
    command, environment = _postgres_command("pg_restore", database_url)
    try:
        subprocess.run(
            [
                *command,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                str(dump_path),
            ],
            check=True,
            env=environment,
        )
    except FileNotFoundError:
        subprocess.run(
            [
                *_docker_postgres_command("pg_restore", database_url),
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
            ],
            input=dump_path.read_bytes(),
            check=True,
        )


def restore_backup(
    *,
    archive_path: str,
    vault_path: str,
    apply: bool = False,
    database_restorer: Callable[[Path], None] | None = None,
) -> RestoreResult:
    archive = Path(archive_path).expanduser()
    vault = Path(vault_path).expanduser()
    if not archive.exists():
        raise FileNotFoundError(str(archive))
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        if any(not _is_safe_zip_member(name) for name in names):
            raise ValueError("Backup archive contains unsafe paths")
        vault_members = [
            name
            for name in names
            if name.startswith("assistantbotmemory/") and not name.endswith("/")
        ]
        database_included = "database/postgres.dump" in names
        if not database_included:
            raise ValueError("Backup archive does not contain a PostgreSQL dump")
        if not apply:
            return RestoreResult(
                archive_path=archive,
                vault_files=len(vault_members),
                database_included=True,
            )
        if database_restorer is None:
            raise ValueError("A database restorer is required when applying a backup")
        vault.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=vault.parent) as temporary:
            staging_root = Path(temporary)
            for name in [*vault_members, "database/postgres.dump"]:
                zf.extract(name, staging_root)
            staged_vault = staging_root / "assistantbotmemory"
            staged_vault.mkdir(parents=True, exist_ok=True)
            dump_path = staging_root / "database" / "postgres.dump"
            database_restorer(dump_path)
            previous_vault: Path | None = None
            if vault.exists():
                timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
                previous_vault = vault.with_name(f"{vault.name}.pre-restore-{timestamp}")
                if previous_vault.exists():
                    raise FileExistsError(str(previous_vault))
                shutil.move(str(vault), str(previous_vault))
            shutil.move(str(staged_vault), str(vault))
            return RestoreResult(
                archive_path=archive,
                vault_files=len(vault_members),
                database_included=True,
                previous_vault_path=previous_vault,
            )


def format_checks(checks: list[CheckResult]) -> str:
    lines = []
    for check in checks:
        mark = "OK" if check.ok else "FAIL"
        lines.append(f"{mark} {check.name}: {check.detail}")
    return "\n".join(lines)


def health_score(checks: list[CheckResult]) -> int:
    if not checks:
        return 100
    ok_count = sum(1 for check in checks if check.ok)
    return round(ok_count / len(checks) * 100)


def format_health_score(checks: list[CheckResult]) -> str:
    score = health_score(checks)
    if score >= 90:
        label = "ready"
    elif score >= 70:
        label = "needs attention"
    else:
        label = "blocked"
    return f"Health score: {score}/100 ({label})"


def repo_root_from_cwd() -> str:
    return os.getcwd()


def _iter_backup_files(vault: Path) -> list[Path]:
    if not vault.exists():
        return []
    return [path for path in vault.rglob("*") if path.is_file()]


def _is_safe_zip_member(name: str) -> bool:
    path = Path(name)
    return not path.is_absolute() and ".." not in path.parts


def _postgres_command(program: str, database_url: str) -> tuple[list[str], dict[str, str]]:
    url = make_url(database_url)
    if not url.database:
        raise ValueError("DATABASE_URL must include a database name")
    environment = os.environ.copy()
    if url.password:
        environment["PGPASSWORD"] = url.password
    command = [program, "--dbname", url.database]
    if url.username:
        command.extend(["--username", url.username])
    if url.host:
        command.extend(["--host", url.host])
    if url.port:
        command.extend(["--port", str(url.port)])
    return command, environment


def _docker_postgres_command(program: str, database_url: str) -> list[str]:
    url = make_url(database_url)
    if not url.database:
        raise ValueError("DATABASE_URL must include a database name")
    if url.host not in {"127.0.0.1", "localhost", "postgres"}:
        raise ValueError(
            "Local Docker PostgreSQL fallback cannot back up an external DATABASE_URL; "
            "install pg_dump for that database."
        )
    command = ["docker", "compose", "exec", "-T", "postgres", program, "--dbname", url.database]
    if url.username:
        command.extend(["--username", url.username])
    return command
