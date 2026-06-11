from __future__ import annotations

import pytest
from app.services.mini_app_state import add_mini_app_task, complete_mini_app_task
from app.services.obsidian_memory import ObsidianMemory

USER_ID = 321


def test_complete_mini_app_task_closes_open_task(tmp_path) -> None:
    vault = str(tmp_path)
    add_mini_app_task(vault_path=vault, user_id=USER_ID, text="проверить задачу")
    memory = ObsidianMemory(vault)
    task = memory.list_open_tasks(user_id=USER_ID, limit=10)[0]

    assert complete_mini_app_task(vault_path=vault, user_id=USER_ID, task_id=task.id) is True
    assert memory.list_open_tasks(user_id=USER_ID, limit=10) == []
    assert complete_mini_app_task(vault_path=vault, user_id=USER_ID, task_id=task.id) is False


def test_complete_mini_app_task_rejects_path_traversal(tmp_path) -> None:
    with pytest.raises(ValueError):
        complete_mini_app_task(vault_path=str(tmp_path), user_id=USER_ID, task_id="../../etc")
    with pytest.raises(ValueError):
        complete_mini_app_task(vault_path=str(tmp_path), user_id=USER_ID, task_id="  ")
