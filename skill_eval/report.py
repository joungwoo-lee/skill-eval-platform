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
    efficiency_uplift: float | None = None  # (C1 효율 / C0 효율) - 1; inf 가능
    efficiency_basis: str = ""              # "성공 횟수 / 총 비용" 또는 "성공 횟수 / 총 시간"
    # 아낀 시간 (기본 측정): C0·C1 둘 다 성공한 쌍 한정, 쌍당 (C0 시간 - C1 시간). 양수 = 스킬이 빠름
    time_saved_mean: float | None = None
    time_saved_pct: float | None = None     # C0 시간 대비 단축 비율
    time_saved_ci: tuple[float, float] | None = None
    n_both_success_pairs: int = 0
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
        s0 = report.conditions.get("C0_NO_SKILL")
        s1 = report.conditions.get("C1_FORCED_SKILL")
        if s0 and s1:
            report.efficiency_uplift, report.efficiency_basis = _efficiency_uplift(s0, s1)

        # 아낀 시간 — 둘 다 성공한 쌍 한정 짝 비교 (기본 측정, PLAN.md §16)
        time_diffs, base_times = _both_success_time_diffs(c0, c1)
        report.n_both_success_pairs = len(time_diffs)
        if time_diffs:
            mean, lo, hi = paired_bootstrap_ci(time_diffs, seed=seed)
            report.time_saved_mean = mean
            report.time_saved_ci = (lo, hi)
            total_base = sum(base_times)
            report.time_saved_pct = sum(time_diffs) / total_base if total_base > 0 else None

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


def _efficiency_uplift(s0: ConditionStats, s1: ConditionStats) -> tuple[float | None, str]:
    """최종 결론 지표: 효율 상승률.

    효율 = 성공 횟수 / 총 비용 (비용 데이터 없으면 총 시간, 그것도 없으면 성공률).
    상승률 = (C1 효율 / C0 효율) - 1. C0 효율이 0인데 C1이 성공하면 inf.
    """
    if s0.total_cost > 0 and s1.total_cost > 0:
        e0, e1, basis = s0.successes / s0.total_cost, s1.successes / s1.total_cost, "성공 횟수 / 총 비용"
    elif s0.total_time > 0 and s1.total_time > 0:
        e0, e1, basis = s0.successes / s0.total_time, s1.successes / s1.total_time, "성공 횟수 / 총 시간"
    else:
        e0, e1, basis = s0.success_rate, s1.success_rate, "성공률"
    if e0 == 0:
        return (float("inf") if e1 > 0 else 0.0), basis
    return (e1 / e0) - 1, basis


def format_uplift(v: float | None) -> str:
    if v is None:
        return "-"
    if v == float("inf"):
        return "+∞%"
    return f"{v:+.1%}"


def _both_success_time_diffs(c0: list[dict], c1: list[dict]) -> tuple[list[float], list[float]]:
    """같은 태스크·같은 반복 회차에서 둘 다 성공한 쌍의 (C0 시간 - C1 시간) 목록.

    성공당 시간 비교는 조건마다 성공한 문제 집합이 달라 왜곡됨 —
    같은 일을 둘 다 해낸 쌍만 봐야 스킬이 아껴준 순수 시간이 나온다.
    반환: (시간차 목록, 해당 쌍의 C0 시간 목록 — 단축률 분모용)
    """
    key = lambda r: (r["task_id"], r["repeat_index"])
    m0 = {key(r): r for r in c0}
    m1 = {key(r): r for r in c1}
    diffs: list[float] = []
    base: list[float] = []
    for k in sorted(set(m0) & set(m1)):
        r0, r1 = m0[k], m1[k]
        if r0["success"] and r1["success"]:
            diffs.append(r0["wall_time"] - r1["wall_time"])
            base.append(r0["wall_time"])
    return diffs, base


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

    # 결론 — 모든 리포트의 최종 지표는 효율 상승 % (단일 값)
    lines.append("## 결론")
    lines.append("")
    if report.efficiency_uplift is not None:
        lines.append(f"**효율 상승: {format_uplift(report.efficiency_uplift)}**")
        note = f"효율 = {report.efficiency_basis}, C0(스킬 없음) 대비 C1(스킬 적용)"
        if report.efficiency_uplift == float("inf"):
            note += " — 스킬 없이는 성공 0"
        lines.append(f"({note})")
    else:
        lines.append("**효율 상승: 측정 불가** (C0/C1 비교 쌍 없음)")
    if report.n_both_success_pairs:
        lo, hi = report.time_saved_ci
        pct = f", C0 대비 {report.time_saved_pct:.0%} 단축" if report.time_saved_pct is not None else ""
        lines.append(
            f"**아낀 시간: 성공 쌍당 평균 {report.time_saved_mean:+.2f}s**"
            f" (둘 다 성공한 쌍 n={report.n_both_success_pairs}{pct},"
            f" 95% CI {lo:+.2f}~{hi:+.2f}s; 양수 = 스킬이 빠름)"
        )
    else:
        lines.append("**아낀 시간: 측정 불가** (둘 다 성공한 쌍 없음)")
    lines.append("")

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

    lines.append("## 구성 지표")
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
