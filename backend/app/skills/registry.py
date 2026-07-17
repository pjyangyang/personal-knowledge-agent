from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    category: str
    top_k: int
    system_prompt: str

    def public_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "top_k": self.top_k,
        }


def load_skills() -> dict[str, SkillDefinition]:
    skills: dict[str, SkillDefinition] = {}
    for path in sorted(Path(__file__).parent.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        skill = SkillDefinition(**data)
        skills[skill.id] = skill
    return skills


SKILLS = load_skills()


def get_skill(skill_id: str | None) -> SkillDefinition:
    selected = SKILLS.get(skill_id or "general_qa")
    if selected is None:
        raise ValueError(f"未知 Skill：{skill_id}")
    return selected
