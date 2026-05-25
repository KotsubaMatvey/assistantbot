from __future__ import annotations

import argparse
from pathlib import Path

from app.config import get_settings
from app.services.admin_tools import restore_backup, restore_postgres_dump


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate or restore an Assistant Bot backup archive."
    )
    parser.add_argument("archive", help="Path to an assistantbot-backup ZIP archive.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the restore. Without this option the command only validates the archive.",
    )
    args = parser.parse_args()
    settings = get_settings()

    database_restorer = None
    if args.apply:
        def apply_database_dump(dump_path: Path) -> None:
            restore_postgres_dump(settings.database_url, dump_path)

        database_restorer = apply_database_dump
    result = restore_backup(
        archive_path=args.archive,
        vault_path=settings.obsidian_vault_path,
        apply=args.apply,
        database_restorer=database_restorer,
        encryption_key=settings.admin_backup_encryption_key,
    )
    mode = "Restored" if args.apply else "Validated"
    print(f"{mode}: {result.vault_files} vault files; database dump present.")
    if result.previous_vault_path is not None:
        print(f"Previous vault retained at: {Path(result.previous_vault_path)}")
    elif not args.apply:
        print("No changes made. Re-run with --apply after taking a fresh backup.")


if __name__ == "__main__":
    main()
