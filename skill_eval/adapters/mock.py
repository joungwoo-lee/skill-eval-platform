"""결정적 시뮬레이션 어댑터.

실제 LLM 없이 파이프라인 전체(러너→검증기→커버리지→통계→리포트)를
엔드투엔드로 검증하기 위한 어댑터. 시드 고정 시 완전 재현된다.

동작 모델:
- 스킬 없음: base_success_rate 확률로 태스크 oracle을 실행(성공 경로).
- 올바른 스킬 로드: skilled_success_rate 확률로 성공. 성공 시 스킬 지침
  이벤트(verify 등)를 궤적에 남긴다. compliance_rate 확률로 지침을 준수.
- Auto Discovery: discovery_accuracy 확률로 올바른 스킬을 선택.
"""
from __future__ import annotations

import random
import subprocess
import sys
import time
from pathlib import Path

from ..models import TrajectoryEvent
from ..registry import SkillPackage, TaskPackage
from .base import AdapterOutcome, AgentAdapter


class MockAdapter(AgentAdapter):
    name = "mock"
    model = "mock-model-v1"

    def __init__(
        self,
        base_success_rate: float = 0.3,
        skilled_success_rate: float = 0.8,
        discovery_accuracy: float = 0.7,
        compliance_rate: float = 0.9,
        tokens_base: int = 4000,
        tokens_skill_overhead: int = 1200,
        cost_per_1k_tokens: float = 0.01,
    ):
        self.base_success_rate = base_success_rate
        self.skilled_success_rate = skilled_success_rate
        self.discovery_accuracy = discovery_accuracy
        self.compliance_rate = compliance_rate
        self.tokens_base = tokens_base
        self.tokens_skill_overhead = tokens_skill_overhead
        self.cost_per_1k_tokens = cost_per_1k_tokens

    def run(
        self,
        task: TaskPackage,
        workdir: Path,
        forced_skill: SkillPackage | None = None,
        skill_pool: list[SkillPackage] | None = None,
        seed: int = 0,
    ) -> AdapterOutcome:
        rng = random.Random((hash(task.task_id) & 0xFFFF) ^ seed)
        out = AdapterOutcome()
        t0 = time.time()
        ev = out.trajectory.append

        active_skill: SkillPackage | None = None
        if forced_skill is not None:
            active_skill = forced_skill
        elif skill_pool:
            # C2: required_skill을 discovery_accuracy 확률로 올바르게 선택
            required = task.required_skill
            correct = next((s for s in skill_pool if s.skill_id == required), None)
            if correct is not None and rng.random() < self.discovery_accuracy:
                active_skill = correct
            elif skill_pool:
                wrong = [s for s in skill_pool if s.skill_id != required]
                if wrong and rng.random() < 0.5:
                    active_skill = rng.choice(wrong)

        tokens = self.tokens_base + rng.randint(-500, 500)
        if active_skill is not None:
            out.skill_was_loaded = True
            out.chosen_skill_id = active_skill.skill_id
            tokens += self.tokens_skill_overhead
            ev(TrajectoryEvent(time.time(), "skill_loaded", "", active_skill.skill_id))

        skill_matches = active_skill is not None and active_skill.skill_id == task.required_skill
        p_success = self.skilled_success_rate if skill_matches else self.base_success_rate
        will_succeed = rng.random() < p_success
        complies = rng.random() < self.compliance_rate

        ev(TrajectoryEvent(time.time(), "model_call", "", f"attempt task {task.task_id}"))

        if will_succeed and task.oracle_script:
            # 성공 경로: oracle을 workdir에서 실행해 실제 산출물을 만든다
            proc = subprocess.run(
                [sys.executable, str(task.oracle_script), str(workdir)],
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode != 0:
                out.error = f"oracle failed: {proc.stderr[:500]}"
                ev(TrajectoryEvent(time.time(), "error", "oracle", out.error))
                will_succeed = False
            else:
                ev(TrajectoryEvent(time.time(), "tool_call", "write_file", "produced deliverable"))
        elif not will_succeed:
            # 실패 경로: 산출물을 만들지 않거나 불완전하게 만든다
            ev(TrajectoryEvent(time.time(), "tool_call", "write_file", "partial attempt, gave up"))

        if skill_matches and will_succeed and complies:
            # 스킬 지침 준수 증거 (constraints.json의 required_pattern과 매칭됨)
            ev(TrajectoryEvent(time.time(), "tool_call", "run_verifier", "self-check verification result ok"))
        elif skill_matches and will_succeed and not complies:
            ev(TrajectoryEvent(time.time(), "note", "", "returned without verification"))

        out.tokens = tokens
        out.cost = round(tokens / 1000 * self.cost_per_1k_tokens, 6)
        ev(TrajectoryEvent(time.time(), "note", "", f"done in {time.time() - t0:.3f}s"))
        return out
