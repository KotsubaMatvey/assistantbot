from __future__ import annotations

import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MAX_IMPORT_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_IMPORT_EXTRACTED_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class MemoryTransferResult:
    path: Path
    files_count: int


def export_user_memory(
    *,
    vault_path: str,
    user_id: int,
    export_dir: str = "exports",
) -> MemoryTransferResult:
    vault = Path(vault_path).expanduser()
    user_dir = vault / "users" / str(user_id)
    destination = vault / export_dir
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"user-{user_id}-memory-{datetime.now(UTC):%Y%m%d-%H%M%S}.zip"
    files_count = 0
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in _iter_files(user_dir):
            zf.write(path, Path("users") / str(user_id) / path.relative_to(user_dir))
            files_count += 1
        zf.writestr(
            "export-info.txt",
            f"user_id={user_id}\ncreated_at={datetime.now(UTC).isoformat()}\n",
        )
        files_count += 1
    return MemoryTransferResult(path=archive, files_count=files_count)


def import_user_memory(
    *,
    vault_path: str,
    user_id: int,
    archive_path: str,
    dry_run: bool = True,
) -> MemoryTransferResult:
    vault = Path(vault_path).expanduser()
    archive = Path(archive_path).expanduser()
    if not archive.exists():
        raise FileNotFoundError(str(archive))
    if archive.stat().st_size > MAX_IMPORT_ARCHIVE_BYTES:
        raise ValueError("Memory archive is too large")
    imported = 0
    extracted_bytes = 0
    target_root = (vault / "users" / str(user_id)).resolve()
    try:
        zf = zipfile.ZipFile(archive)
    except zipfile.BadZipFile as exc:
        raise ValueError("Memory archive is not a valid ZIP file") from exc
    with zf:
        for info in zf.infolist():
            name = info.filename
            if name.endswith("/") or not _is_safe_zip_member(name):
                continue
            extracted_bytes += info.file_size
            if extracted_bytes > MAX_IMPORT_EXTRACTED_BYTES:
                raise ValueError("Memory archive contents are too large")
            parts = Path(name).parts
            if len(parts) >= 3 and parts[0] == "users" and parts[1].isdigit():
                relative = Path(*parts[2:])
            else:
                relative = Path(name)
            target = (target_root / relative).resolve()
            if not _is_relative_to(target, target_root):
                continue
            imported += 1
            if dry_run:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
    return MemoryTransferResult(path=archive, files_count=imported)


def _iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [path for path in root.rglob("*") if path.is_file()]


def _is_safe_zip_member(name: str) -> bool:
    path = Path(name)
    return not path.is_absolute() and ".." not in path.parts


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
