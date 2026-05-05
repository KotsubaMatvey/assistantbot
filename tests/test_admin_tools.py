from __future__ import annotations

import zipfile

from app.services.admin_tools import (
    check_docker_compose,
    check_secret_files,
    check_vault,
    create_backup,
)


def test_check_vault_creates_and_tests_directory(tmp_path) -> None:
    check = check_vault(str(tmp_path / "memory"))

    assert check.ok is True
    assert (tmp_path / "memory").exists()


def test_check_secret_files_requires_env_in_gitignore(tmp_path) -> None:
    (tmp_path / ".env").write_text("BOT_TOKEN=secret", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")

    assert check_secret_files(str(tmp_path)).ok is True


def test_check_docker_compose_reports_restart_policy(tmp_path) -> None:
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  bot:\n    restart: unless-stopped\n    volumes:\n"
        "      - ./assistantbotmemory:/app/assistantbotmemory\n",
        encoding="utf-8",
    )

    checks = check_docker_compose(str(tmp_path))

    assert all(check.ok for check in checks)


def test_create_backup_includes_memory_and_safe_project_files(tmp_path) -> None:
    vault = tmp_path / "assistantbotmemory"
    vault.mkdir()
    (vault / "note.md").write_text("memory", encoding="utf-8")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    (tmp_path / ".env").write_text("BOT_TOKEN=secret", encoding="utf-8")

    result = create_backup(repo_root=str(tmp_path), vault_path=str(vault))

    with zipfile.ZipFile(result.path) as archive:
        names = set(archive.namelist())
    assert "assistantbotmemory/note.md" in names
    assert "project/README.md" in names
    assert ".env" not in names
