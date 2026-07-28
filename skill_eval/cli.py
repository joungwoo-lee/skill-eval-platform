"""CLI 진입점.

사용 예:
  skill-eval list --skills-dir skills --tasks-dir tasks
  skill-eval run --task tasks/demo/hello-report-001 --skill skills/demo-report/1.0.0 \\
      --conditions C0,C1,C2 --repeats 5 --adapter mock --db results/results.db
  skill-eval report --db results/results.db --out results/report.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .adapters.claude_code import ClaudeCodeAdapter
from .adapters.mock import MockAdapter
from .analyzers.coverage import compute_coverage
from .models import Store
from .registry import SkillPackage, TaskPackage, discover_skills, discover_tasks
from .report import build_report, render_markdown
from .runners.runner import ExperimentRunner

_COND_ALIAS = {
    "C0": "C0_NO_SKILL",
    "C1": "C1_FORCED_SKILL",
    "C2": "C2_AUTO_DISCOVERY",
}


def _cmd_list(args: argparse.Namespace) -> int:
    for s in discover_skills(args.skills_dir):
        print(f"skill  {s.skill_id}@{s.version}  constraints={len(s.constraints)}")
    for t in discover_tasks(args.tasks_dir):
        print(f"task   {t.domain}/{t.task_id}  required_skill={t.required_skill}")
    return 0


def _make_adapter(args: argparse.Namespace):
    if args.adapter == "mock":
        return MockAdapter()
    if args.adapter == "claude-code":
        return ClaudeCodeAdapter(model=args.model)
    raise SystemExit(f"unknown adapter: {args.adapter}")


def _cmd_run(args: argparse.Namespace) -> int:
    task = TaskPackage.load(args.task)
    skill = SkillPackage.load(args.skill) if args.skill else None
    conditions = [_COND_ALIAS.get(c.strip(), c.strip()) for c in args.conditions.split(",")]
    distractors = [SkillPackage.load(p) for p in (args.distractor or [])]

    store = Store(args.db)
    runner = ExperimentRunner(store, _make_adapter(args))
    results = runner.run_conditions(
        task, skill, conditions, repeats=args.repeats, seed=args.seed,
        distractor_skills=distractors,
    )
    ok = sum(r.success for r in results)
    print(f"{len(results)} runs finished, {ok} succeeded → {args.db}")
    store.close()
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    store = Store(args.db)
    coverage = None
    if args.skill:
        skill = SkillPackage.load(args.skill)
        if skill.constraints:
            verdict_rows = store.load_constraint_results()
            by_run: dict[str, dict[str, str]] = {}
            for row in verdict_rows:
                by_run.setdefault(row["run_id"], {})[row["constraint_id"]] = row["verdict"]
            coverage = compute_coverage(list(by_run.values()), len(skill.constraints))
    report = build_report(store, coverage=coverage)
    md = render_markdown(report)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"report written → {args.out}")
    else:
        print(md)
    store.close()
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    """복수 스킬 일괄 평가: 스킬별 DB·리포트 생성 + summary.md."""
    skills = [SkillPackage.load(p) for p in args.skill]
    all_tasks = discover_tasks(args.tasks_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    conditions = [_COND_ALIAS.get(c.strip(), c.strip()) for c in args.conditions.split(",")]

    summary: list[tuple] = []
    for skill in skills:
        tasks = [t for t in all_tasks if t.required_skill == skill.skill_id]
        if not tasks:
            print(f"[skip] {skill.skill_id}: required_skill 매칭 태스크 없음 ({args.tasks_dir})")
            summary.append((skill.skill_id, 0, None, None))
            continue
        db = out_dir / f"{skill.skill_id}.db"
        if db.exists():
            db.unlink()
        store = Store(db)
        runner = ExperimentRunner(store, _make_adapter(args))
        distractors = [s for s in skills if s.skill_id != skill.skill_id]
        for task in tasks:
            runner.run_conditions(
                task, skill, conditions, repeats=args.repeats,
                seed=args.seed, distractor_skills=distractors,
            )
        coverage = None
        if skill.constraints:
            by_run: dict[str, dict[str, str]] = {}
            for row in store.load_constraint_results():
                by_run.setdefault(row["run_id"], {})[row["constraint_id"]] = row["verdict"]
            coverage = compute_coverage(list(by_run.values()), len(skill.constraints))
        report = build_report(store, coverage=coverage)
        md_path = out_dir / f"{skill.skill_id}.md"
        md_path.write_text(
            render_markdown(report, title=f"Skill Evaluation — {skill.skill_id}@{skill.version}"),
            encoding="utf-8",
        )
        summary.append((skill.skill_id, len(tasks), report.skill_lift, report.operational_lift))
        print(f"[done] {skill.skill_id}: tasks={len(tasks)} → {md_path}")
        store.close()

    fmt = lambda v: f"{v:+.1%}" if v is not None else "-"
    lines = ["# Skill Eval Batch Summary", "",
             "| 스킬 | 태스크 | Skill Lift | Operational Lift |", "|---|---|---|---|"]
    for sid, ntasks, lift, oplift in summary:
        lines.append(f"| {sid} | {ntasks} | {fmt(lift)} | {fmt(oplift)} |")
    text = "\n".join(lines) + "\n"
    (out_dir / "summary.md").write_text(text, encoding="utf-8")
    print()
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows cp949 콘솔에서 한글 리포트 깨짐 방지
    parser = argparse.ArgumentParser(prog="skill-eval", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="스킬·태스크 레지스트리 나열")
    p_list.add_argument("--skills-dir", default="skills")
    p_list.add_argument("--tasks-dir", default="tasks")
    p_list.set_defaults(func=_cmd_list)

    p_run = sub.add_parser("run", help="실험 실행")
    p_run.add_argument("--task", required=True, help="태스크 패키지 디렉토리")
    p_run.add_argument("--skill", help="대상 스킬 디렉토리 (skills/<id>/<version>)")
    p_run.add_argument("--distractor", action="append", help="C2용 무관 스킬 디렉토리 (반복 가능)")
    p_run.add_argument("--conditions", default="C0,C1", help="쉼표구분: C0,C1,C2")
    p_run.add_argument("--repeats", type=int, default=3)
    p_run.add_argument("--seed", type=int, default=0)
    p_run.add_argument("--adapter", default="mock", choices=["mock", "claude-code"])
    p_run.add_argument("--model", default="claude-sonnet-5")
    p_run.add_argument("--db", default="results/results.db")
    p_run.set_defaults(func=_cmd_run)

    p_batch = sub.add_parser("batch", help="복수 스킬 일괄 평가 (스킬별 리포트 + summary.md)")
    p_batch.add_argument("--skill", action="append", required=True,
                         help="스킬 디렉토리 skills/<id>/<version> (반복 가능)")
    p_batch.add_argument("--tasks-dir", default="tasks")
    p_batch.add_argument("--conditions", default="C0,C1")
    p_batch.add_argument("--repeats", type=int, default=3)
    p_batch.add_argument("--seed", type=int, default=0)
    p_batch.add_argument("--adapter", default="mock", choices=["mock", "claude-code"])
    p_batch.add_argument("--model", default="claude-sonnet-5")
    p_batch.add_argument("--out-dir", default="results/batch")
    p_batch.set_defaults(func=_cmd_batch)

    p_rep = sub.add_parser("report", help="지표 계산·리포트 생성")
    p_rep.add_argument("--db", default="results/results.db")
    p_rep.add_argument("--skill", help="커버리지 계산용 스킬 디렉토리")
    p_rep.add_argument("--out", help="마크다운 출력 경로 (생략 시 stdout)")
    p_rep.set_defaults(func=_cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
