"""에이전트 어댑터 인터페이스 (PLAN.md §15 adapters/).

어댑터는 태스크를 작업 디렉토리에서 실행하고 궤적·토큰·비용을 보고한다.
성공 판정은 어댑터가 아니라 결정적 검증기가 한다 (PLAN.md §2.3).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ..models import TrajectoryEvent
from ..registry import SkillPackage, TaskPackage


@dataclass
class AdapterOutcome:
    trajectory: list[TrajectoryEvent] = field(default_factory=list)
    tokens: int = 0
    cost: float = 0.0
    skill_was_loaded: bool = False
    chosen_skill_id: str | None = None
    error: str = ""


class AgentAdapter(ABC):
    """단일 태스크 1회 실행 인터페이스."""

    name = "base"
    model = "unknown"

    @abstractmethod
    def run(
        self,
        task: TaskPackage,
        workdir: Path,
        forced_skill: SkillPackage | None = None,
        skill_pool: list[SkillPackage] | None = None,
        seed: int = 0,
    ) -> AdapterOutcome:
        """태스크 실행.

        forced_skill: C1 조건 — 이 스킬을 강제 로드.
        skill_pool: C2 조건 — 에이전트가 이 풀에서 스스로 선택.
        둘 다 None이면 C0 (No Skill).
        """
        raise NotImplementedError
