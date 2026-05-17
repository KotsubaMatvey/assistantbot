from __future__ import annotations

from app.services.file_io import atomic_write_text


def test_atomic_write_text_replaces_existing_file(tmp_path) -> None:
    path = tmp_path / "store" / "data.json"

    atomic_write_text(path, '{"version": 1}')
    atomic_write_text(path, '{"version": 2}')

    assert path.read_text(encoding="utf-8") == '{"version": 2}'
    assert list(path.parent.glob("*.tmp")) == []
