"""스킬·태스크 레지스트리 (PLAN.md §5, §6).

skills/<skill-id>/<version>/SKILL.md (+ constraints.json, scripts/, references/)
tasks/<domain>/<task-id>/{task.md, metadata.yaml, environment/initial_state/, verifier/, oracle/, hidden_tests/}
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SkillPackage:
    skill_id: str
    version: str
    root: Path
    skill_md: str
    constraints: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, root: str | Path) -> "SkillPackage":
        root = Path(root)
        skill_md_path = root / "SKILL.md"
        if not skill_md_path.exists():
            raise FileNotFoundError(f"SKILL.md not found in {root}")
        constraints_path = root / "constraints.json"
        constraints = (
            json.loads(constraints_path.read_text(encoding="utf-8"))
            if constraints_path.exists()
            else []
        )
        return cls(
            skill_id=root.parent.name,
            version=root.name,
            root=root,
            skill_md=skill_md_path.read_text(encoding="utf-8"),
            constraints=constraints,
        )


@dataclass
class TaskPackage:
    task_id: str
    domain: str
    root: Path
    task_md: str
    metadata: dict[str, Any]

    @classmethod
    def load(cls, root: str | Path) -> "TaskPackage":
        root = Path(root)
        meta_path = root / "metadata.yaml"
        metadata = yaml.safe_load(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        return cls(
            task_id=metadata.get("task_id", root.name),
            domain=metadata.get("domain", root.parent.name),
            root=root,
            task_md=(root / "task.md").read_text(encoding="utf-8"),
            metadata=metadata,
        )

    @property
    def initial_state_dir(self) -> Path:
        return self.root / "environment" / "initial_state"

    @property
    def verifier_script(self) -> Path:
        rel = self.metadata.get("success", {}).get("verifier", "verifier/score.py")
        return self.root / rel

    @property
    def oracle_script(self) -> Path | None:
        p = self.root / "oracle" / "solve.py"
        return p if p.exists() else None

    @property
    def minimum_score(self) -> float:
        return float(self.metadata.get("success", {}).get("minimum_score", 1.0))

    @property
    def required_skill(self) -> str | None:
        return self.metadata.get("required_skill")


def discover_skills(skills_dir: str | Path) -> list[SkillPackage]:
    """skills/<id>/<version>/ 전체 스캔. 버전 정렬 후 반환."""
    out: list[SkillPackage] = []
    skills_dir = Path(skills_dir)
    if not skills_dir.exists():
        return out
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        for ver_dir in sorted(skill_dir.iterdir()):
            if ver_dir.is_dir() and (ver_dir / "SKILL.md").exists():
                out.append(SkillPackage.load(ver_dir))
    return out


def discover_tasks(tasks_dir: str | Path) -> list[TaskPackage]:
    """tasks/<domain>/<task-id>/ 전체 스캔."""
    out: list[TaskPackage] = []
    tasks_dir = Path(tasks_dir)
    if not tasks_dir.exists():
        return out
    for domain_dir in sorted(tasks_dir.iterdir()):
        if not domain_dir.is_dir():
            continue
        for task_dir in sorted(domain_dir.iterdir()):
            if task_dir.is_dir() and (task_dir / "task.md").exists():
                out.append(TaskPackage.load(task_dir))
    return out


def latest_version(skills: list[SkillPackage], skill_id: str) -> SkillPackage | None:
    matches = [s for s in skills if s.skill_id == skill_id]
    return matches[-1] if matches else None
