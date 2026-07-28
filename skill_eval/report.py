"""핵심 지표 계산과 마크다운 리포트 (PLAN.md §10, §16).

- Skill Lift = P(success | C1) - P(success | C0)
- Time/Cost per Success, 커버리지, 실패 유형 분포, 신뢰구간(짝지은 부트스트랩), McNemar
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .models import Store
from .statistics.mcnemar import mcnemar_exact, paired_success_table
from .statistics.paired_bootstrap import paired_bootstrap_ci


@dataclass
class ConditionStats:
    n: int = 0
    successes: int = 0
    total_time: float = 0.0
    total_cost: float = 0.0
    total_tokens: int = 0

    @property
    def success_rate(self) -> float:
        return self.successes / self.n if self.n else 0.0

    @property
    def time_per_success(self) -> float | None:
        return self.total_time / self.successes if self.successes else None

    @property
    def cost_per_success(self) -> float | None:
        return self.total_cost / self.successes if self.successes else None


@dataclass
class Report:
    conditions: dict[str, ConditionStats] = field(default_factory=dict)
    skill_lift: float | None = None
    skill_lift_ci: tuple[float, float] | None = None
    skill_lift_pvalue: float | None = None
    failure_modes: dict[str, int] = field(default_factory=dict)
    coverage: dict | None = None


def _per_task_diff(runs_a: list[dict], runs_b: list[dict]) -> list[float]:
    """태스크별 성공률 차이 (b - a)."""
    by_task_a: dict[str, list[int]] = defaultdict(list)
    by_task_b: dict[str, list[int]] = defaultdict(list)
    for r in runs_a:
        by_task_a[r["task_id"]].append(r["success"])
    for r in runs_b:
        by_task_b[r["task_id"]].append(r["success"])
    diffs = []
    for task_id in sorted(set(by_task_a) & set(by_task_b)):
        pa = sum(by_task_a[task_id]) / len(by_task_a[task_id])
        pb = sum(by_task_b[task_id]) / len(by_task_b[task_id])
        diffs.append(pb - pa)
    return diffs


def build_report(store: Store, coverage: dict | None = None, seed: int = 42) -> Report:
    report = Report(coverage=coverage)
    all_runs = store.load_runs()

    for run in all_runs:
        cs = report.conditions.setdefault(run["condition"], ConditionStats())
        cs.n += 1
        cs.successes += run["success"]
        cs.total_time += run["wall_time"]
        cs.total_cost += run["cost"]
        cs.total_tokens += run["tokens"]

    c0 = [r for r in all_runs if r["condition"] == "C0_NO_SKILL"]
    c1 = [r for r in all_runs if r["condition"] == "C1_FORCED_SKILL"]

    if c0 and c1:
        diffs = _per_task_diff(c0, c1)
        mean, lo, hi = paired_bootstrap_ci(diffs, seed=seed)
        report.skill_lift = mean
        report.skill_lift_ci = (lo, hi)
        # McNemar: repeat_index로 짝 맞춤 (동일 태스크·동일 반복 인덱스)
        paired_a, paired_b = _pair_by_repeat(c0, c1)
        if paired_a:
            _, a_only, b_only, _ = paired_success_table(paired_a, paired_b)
            report.skill_lift_pvalue = mcnemar_exact(a_only, b_only)

    for f in store.load_failures():
        report.failure_modes[f["failure_type"]] = report.failure_modes.get(f["failure_type"], 0) + 1

    return report


def _pair_by_repeat(runs_a: list[dict], runs_b: list[dict]) -> tuple[list[bool], list[bool]]:
    key = lambda r: (r["task_id"], r["repeat_index"])
    map_a = {key(r): bool(r["success"]) for r in runs_a}
    map_b = {key(r): bool(r["success"]) for r in runs_b}
    common = sorted(set(map_a) & set(map_b))
    return [map_a[k] for k in common], [map_b[k] for k in common]


_COND_LABEL = {
    "C0_NO_SKILL": "C0 No Skill",
    "C1_FORCED_SKILL": "C1 Forced Skill",
}


def render_markdown(report: Report, title: str = "Skill Evaluation Report") -> str:
    lines = [f"# {title}", ""]

    lines += ["## 조건별 결과", "",
              "| 조건 | 실행 | 성공률 | 성공당 시간(s) | 성공당 비용($) | 총 토큰 |",
              "|---|---|---|---|---|---|"]
    for cond in sorted(report.conditions):
        cs = report.conditions[cond]
        tps = f"{cs.time_per_success:.2f}" if cs.time_per_success is not None else "-"
        cps = f"{cs.cost_per_success:.4f}" if cs.cost_per_success is not None else "-"
        lines.append(
            f"| {_COND_LABEL.get(cond, cond)} | {cs.n} | {cs.success_rate:.1%} | {tps} | {cps} | {cs.total_tokens:,} |"
        )
    lines.append("")

    lines.append("## 핵심 지표")
    lines.append("")
    if report.skill_lift is not None:
        lo, hi = report.skill_lift_ci
        p = f", McNemar p={report.skill_lift_pvalue:.4f}" if report.skill_lift_pvalue is not None else ""
        lines.append(f"- **Skill Lift**: {report.skill_lift:+.1%} (95% CI {lo:+.1%} ~ {hi:+.1%}{p})")
    else:
        lines.append("- (비교 가능한 조건 쌍 없음)")
    lines.append("")

    if report.coverage:
        lines += ["## Skill Coverage", "",
                  f"- 커버리지: **{report.coverage['coverage']:.1%}**",
                  f"- 검증된 제약: {', '.join(report.coverage['covered_constraints']) or '없음'}",
                  f"- 미검증 제약: {', '.join(report.coverage['unverified_constraints']) or '없음'}"]
        if report.coverage.get("fail_counts"):
            lines.append(f"- 위반 발생: {report.coverage['fail_counts']}")
        lines.append("")

    if report.failure_modes:
        lines += ["## 실패 유형 분포", "", "| 유형 | 건수 |", "|---|---|"]
        for ft, n in sorted(report.failure_modes.items(), key=lambda x: -x[1]):
            lines.append(f"| {ft} | {n} |")
        lines.append("")

    return "\n".join(lines)
