from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SKILLS = {
    "secretary": "Use this mode to extract tasks, reminders, decisions, and follow-ups.",
    "researcher": "Use this mode to summarize sources, keep citations, and connect notes.",
    "editor": "Use this mode to rewrite drafts clearly while preserving intent.",
    "analyst": "Use this mode to compare options, risks, assumptions, and next steps.",
}


@dataclass(frozen=True)
class AssistantSkill:
    name: str
    path: Path
    description: str


class AssistantSkillStore:
    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()
        self.skills_dir = self.vault_path / "skills"

    def ensure_default_skills(self) -> None:
        for name, description in DEFAULT_SKILLS.items():
            path = self._skill_path(name)
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_skill_markdown(name=name, description=description), encoding="utf-8")

    def list_skills(self) -> list[AssistantSkill]:
        self.ensure_default_skills()
        if not self.skills_dir.exists():
            return []
        skills: list[AssistantSkill] = []
        for skill_dir in sorted(self.skills_dir.iterdir()):
            path = skill_dir / "SKILL.md"
            if not skill_dir.is_dir() or not path.exists():
                continue
            skills.append(
                AssistantSkill(
                    name=skill_dir.name,
                    path=path,
                    description=_first_body_line(path.read_text(encoding="utf-8", errors="ignore")),
                )
            )
        return skills

    def get_skill(self, name: str) -> AssistantSkill | None:
        normalized = normalize_skill_name(name)
        path = self._skill_path(normalized)
        if not path.exists():
            return None
        return AssistantSkill(
            name=normalized,
            path=path,
            description=_first_body_line(path.read_text(encoding="utf-8", errors="ignore")),
        )

    def create_skill(self, *, name: str, instructions: str) -> AssistantSkill:
        normalized = normalize_skill_name(name)
        clean = instructions.strip()
        if not clean:
            raise ValueError("skill instructions are empty")
        path = self._skill_path(normalized)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_skill_markdown(name=normalized, description=clean), encoding="utf-8")
        return AssistantSkill(name=normalized, path=path, description=clean.splitlines()[0])

    def active_skill_name(self, *, user_id: int) -> str | None:
        path = self._active_skill_path(user_id)
        if not path.exists():
            return None
        name = normalize_skill_name(path.read_text(encoding="utf-8", errors="ignore"))
        return name or None

    def set_active_skill(self, *, user_id: int, name: str) -> AssistantSkill:
        skill = self.get_skill(name)
        if skill is None:
            raise ValueError("skill not found")
        path = self._active_skill_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(skill.name, encoding="utf-8")
        return skill

    def _skill_path(self, name: str) -> Path:
        return self.skills_dir / normalize_skill_name(name) / "SKILL.md"

    def _active_skill_path(self, user_id: int) -> Path:
        return self.vault_path / "users" / str(user_id) / "active-skill.txt"


def normalize_skill_name(name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
    return normalized


def _skill_markdown(*, name: str, description: str) -> str:
    return f"---\nname: {name}\n---\n\n{description.strip()}\n"


def _first_body_line(text: str) -> str:
    body = text.split("---", 2)[2] if text.startswith("---") and text.count("---") >= 2 else text
    for line in body.splitlines():
        clean = line.strip()
        if clean:
            return clean[:160]
    return ""
