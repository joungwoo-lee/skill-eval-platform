"""엔드투엔드: 데모 태스크 × MockAdapter로 C0/C1/C2 실행 → 리포트 생성.

파이프라인 전 구간(레지스트리→러너→검증기→커버리지→실패분류→통계→리포트) 검증.
"""
from pathlib import Path

import pytest

from skill_eval.adapters.mock import MockAdapter
from skill_eval.analyzers.coverage import compute_coverage
from skill_eval.models import Store
from skill_eval.registry import SkillPackage, TaskPackage, discover_skills, discover_tasks
from skill_eval.report import build_report, render_markdown
from skill_eval.runners.runner import ExperimentRunner

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def task():
    return TaskPackage.load(ROOT / "tasks" / "demo" / "hello-report-001")


@pytest.fixture()
def skill():
    return SkillPackage.load(ROOT / "skills" / "demo-report" / "1.0.0")


@pytest.fixture()
def distractor():
    return SkillPackage.load(ROOT / "skills" / "demo-distractor" / "1.0.0")


def test_registry_discovery():
    skills = discover_skills(ROOT / "skills")
    tasks = discover_tasks(ROOT / "tasks")
    assert {s.skill_id for s in skills} >= {"demo-report", "demo-distractor"}
    assert any(t.task_id == "hello-report-001" for t in tasks)


def test_verifier_scores_oracle_output(task, tmp_path):
    import subprocess
    import sys
    import shutil

    shutil.copytree(task.initial_state_dir, tmp_path, dirs_exist_ok=True)
    subprocess.run([sys.executable, str(task.oracle_script), str(tmp_path)], check=True)
    from skill_eval.evaluators.deterministic import run_verifier

    vr = run_verifier(task.verifier_script, tmp_path, task.minimum_score)
    assert vr.success and vr.score == 1.0


def test_verifier_fails_empty_workdir(task, tmp_path):
    import shutil

    shutil.copytree(task.initial_state_dir, tmp_path, dirs_exist_ok=True)
    from skill_eval.evaluators.deterministic import run_verifier

    vr = run_verifier(task.verifier_script, tmp_path, task.minimum_score)
    assert not vr.success


def test_end_to_end_lift_and_report(task, skill, distractor, tmp_path):
    store = Store(tmp_path / "results.db")
    adapter = MockAdapter(base_success_rate=0.2, skilled_success_rate=0.95,
                          discovery_accuracy=0.8, compliance_rate=0.85)
    runner = ExperimentRunner(store, adapter)
    results = runner.run_conditions(
        task, skill,
        conditions=["C0_NO_SKILL", "C1_FORCED_SKILL", "C2_AUTO_DISCOVERY"],
        repeats=20, seed=7, distractor_skills=[distractor],
    )
    assert len(results) == 60

    # 커버리지 집계
    verdict_rows = store.load_constraint_results()
    by_run: dict[str, dict[str, str]] = {}
    for row in verdict_rows:
        by_run.setdefault(row["run_id"], {})[row["constraint_id"]] = row["verdict"]
    coverage = compute_coverage(list(by_run.values()), len(skill.constraints))

    report = build_report(store, coverage=coverage)

    # 시드 고정 시뮬레이션: 스킬 조건이 확실히 우세해야 한다
    assert report.skill_lift is not None and report.skill_lift > 0.3
    assert report.operational_lift is not None
    assert report.skill_lift_pvalue is not None and report.skill_lift_pvalue < 0.05
    assert report.conditions["C1_FORCED_SKILL"].success_rate > report.conditions["C0_NO_SKILL"].success_rate
    assert coverage["coverage"] > 0

    md = render_markdown(report)
    assert "Skill Lift" in md and "조건별 결과" in md

    # 실패 유형이 하나 이상 분류되어야 한다 (C0 실패 다수)
    assert report.failure_modes
    store.close()


def test_ablation_condition_runs(task, skill, tmp_path):
    store = Store(tmp_path / "results.db")
    runner = ExperimentRunner(store, MockAdapter())
    results = runner.run_conditions(task, skill, ["C3_ABLATION"], repeats=3, seed=1)
    assert len(results) == 3
    assert all(r.condition == "C3_ABLATION" for r in results)
    store.close()


def test_cli_smoke(tmp_path):
    from skill_eval.cli import main

    db = tmp_path / "r.db"
    rc = main([
        "run",
        "--task", str(ROOT / "tasks" / "demo" / "hello-report-001"),
        "--skill", str(ROOT / "skills" / "demo-report" / "1.0.0"),
        "--conditions", "C0,C1",
        "--repeats", "3",
        "--adapter", "mock",
        "--db", str(db),
    ])
    assert rc == 0
    out = tmp_path / "report.md"
    rc = main([
        "report", "--db", str(db),
        "--skill", str(ROOT / "skills" / "demo-report" / "1.0.0"),
        "--out", str(out),
    ])
    assert rc == 0
    assert "Skill Lift" in out.read_text(encoding="utf-8")
