"""실험 러너 (PLAN.md §5, §7, §8).

한 번의 run = 초기 상태 복사 → 어댑터 실행 → 결정적 검증 → 커버리지 판정
→ 실패 원인 분류 → 저장. 실행 순서는 조건×반복을 시드 기반으로 무작위화한다 (§8).
"""
from __future__ import annotations

import random
import shutil
import tempfile
import time
from pathlib import Path

from ..adapters.base import AgentAdapter
from ..analyzers.coverage import judge_constraints
from ..analyzers.failure import attribute_failure
from ..evaluators.deterministic import run_verifier
from ..models import ExperimentSpec, RunResult, Store, new_id
from ..registry import SkillPackage, TaskPackage


class ExperimentRunner:
    def __init__(self, store: Store, adapter: AgentAdapter, results_dir: str | Path | None = None):
        self.store = store
        self.adapter = adapter
        self.results_dir = Path(results_dir) if results_dir else None

    def _fresh_workdir(self, task: TaskPackage) -> Path:
        workdir = Path(tempfile.mkdtemp(prefix=f"run-{task.task_id}-"))
        if task.initial_state_dir.exists():
            shutil.copytree(task.initial_state_dir, workdir, dirs_exist_ok=True)
        return workdir

    def run_once(
        self,
        spec: ExperimentSpec,
        task: TaskPackage,
        repeat_index: int,
        forced_skill: SkillPackage | None = None,
        skill_pool: list[SkillPackage] | None = None,
    ) -> RunResult:
        run = RunResult(
            run_id=new_id("run"),
            experiment_id=spec.experiment_id,
            condition=spec.condition,
            task_id=task.task_id,
            skill_id=spec.skill_id,
            skill_version=spec.skill_version,
            model=self.adapter.model,
            repeat_index=repeat_index,
        )
        workdir = self._fresh_workdir(task)
        try:
            run.started_at = time.time()
            outcome = self.adapter.run(
                task, workdir,
                forced_skill=forced_skill,
                skill_pool=skill_pool,
                seed=spec.seed + repeat_index,
            )
            run.finished_at = time.time()
            run.wall_time = run.finished_at - run.started_at
            run.trajectory = outcome.trajectory
            run.tokens = outcome.tokens
            run.cost = outcome.cost
            run.skill_was_loaded = outcome.skill_was_loaded

            vr = run_verifier(task.verifier_script, workdir, task.minimum_score)
            run.score = vr.score
            run.success = vr.success
            run.verifier_error = vr.error

            constraints = (forced_skill.constraints if forced_skill else None) or (
                next((s.constraints for s in (skill_pool or [])
                      if s.skill_id == outcome.chosen_skill_id), [])
            )
            if constraints:
                run.constraint_verdicts = judge_constraints(constraints, run.trajectory)

            if not run.success:
                skill_expected = spec.condition in ("C1_FORCED_SKILL", "C2_AUTO_DISCOVERY", "C3_ABLATION")
                run.failure_type, run.failure_rationale = attribute_failure(run, skill_expected)

            self.store.save_run(run)
            return run
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def run_conditions(
        self,
        task: TaskPackage,
        skill: SkillPackage | None,
        conditions: list[str],
        repeats: int,
        seed: int = 0,
        distractor_skills: list[SkillPackage] | None = None,
    ) -> list[RunResult]:
        """조건 목록 × 반복을 무작위 순서로 실행 (§8)."""
        specs: dict[str, ExperimentSpec] = {}
        for cond in conditions:
            spec = ExperimentSpec(
                experiment_id=new_id("exp"),
                task_id=task.task_id,
                skill_id=skill.skill_id if skill else None,
                skill_version=skill.version if skill else None,
                condition=cond,
                model=self.adapter.model,
                harness=self.adapter.name,
                seed=seed,
                repeats=repeats,
                limits=task.metadata.get("limits", {}),
            )
            self.store.save_experiment(spec)
            specs[cond] = spec

        schedule = [(cond, i) for cond in conditions for i in range(repeats)]
        random.Random(seed).shuffle(schedule)

        pool = ([skill] if skill else []) + (distractor_skills or [])
        results: list[RunResult] = []
        for cond, i in schedule:
            forced = skill if cond in ("C1_FORCED_SKILL",) else None
            if cond == "C3_ABLATION" and skill:
                forced = skill.ablated("scripts")
            skill_pool = pool if cond == "C2_AUTO_DISCOVERY" else None
            results.append(self.run_once(specs[cond], task, i, forced, skill_pool))
        return results
