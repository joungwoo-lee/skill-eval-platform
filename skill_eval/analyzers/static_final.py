"""최종 정적 평가 — 패턴 채점과 LLM 판정을 비교·합성한다.

- 공유 6항목(trigger/steps/vagueness/verification/recovery/output_spec):
  패턴과 LLM이 같은 항목을 따로 채점 → 비교표에 나란히, 최종 = 평균.
  두 점수 차이가 크면(≥0.4) 괴리로 플래그 — 패턴 오탐/미탐 또는 LLM 환각 후보.
- LLM 전용 3항목(content_validity/consistency/sufficiency): LLM 점수 그대로.
- 패턴 전용 3항목(resources/overhead/constraints): 파일시스템·분량 기반이라 패턴 그대로.

최종 결론 = 합성 가중 점수(0~100) → 추정 효율 상승 % (static_lint와 같은 앵커).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .llm_judge import LLM_ONLY_DIMS, RUBRIC, SHARED_DIMS, LlmJudgeResult
from .static_lint import LintReport

DIVERGENCE_THRESHOLD = 0.4

_DIM_NAMES = {
    "trigger": "발동 조건 구체성", "steps": "단계화된 지침", "vagueness": "모호어(구체성)",
    "verification": "자체 검증 절차", "recovery": "오류·실패 대응", "output_spec": "산출물·형식 명시",
    "content_validity": "내용 타당성", "consistency": "내부 일관성", "sufficiency": "절차 충분성",
    "resources": "동봉 자원 일치", "overhead": "분량 오버헤드", "constraints": "행동 제약 정의",
}
_LLM_ONLY_WEIGHT = 1.5


@dataclass
class DimComparison:
    dim: str
    name: str
    weight: float
    pattern_score: float | None
    llm_score: float | None
    final_score: float
    divergent: bool = False


@dataclass
class FinalStaticReport:
    skill_id: str
    version: str
    comparisons: list[DimComparison] = field(default_factory=list)
    llm: LlmJudgeResult | None = None
    pattern: LintReport | None = None

    @property
    def total_score(self) -> float:
        total_w = sum(c.weight for c in self.comparisons)
        if not total_w:
            return 0.0
        return round(100 * sum(c.final_score * c.weight for c in self.comparisons) / total_w, 1)

    @property
    def est_efficiency_uplift(self) -> float:
        anchor = (self.pattern.ANCHOR_UPLIFT if self.pattern else LintReport.ANCHOR_UPLIFT)
        return round(self.total_score / 100 * anchor, 3)

    @property
    def divergences(self) -> list[DimComparison]:
        return [c for c in self.comparisons if c.divergent]


def combine_static(pattern: LintReport, llm: LlmJudgeResult) -> FinalStaticReport:
    report = FinalStaticReport(pattern.skill_id, pattern.version, llm=llm, pattern=pattern)
    pattern_by_id = {c.check_id: c for c in pattern.checks}

    for dim in SHARED_DIMS:
        pc = pattern_by_id.get(dim)
        p_score = pc.score if pc else None
        l_score = llm.scores.get(dim)
        final = ((p_score or 0.0) + (l_score or 0.0)) / 2 if (p_score is not None and l_score is not None) \
            else (l_score if l_score is not None else (p_score or 0.0))
        report.comparisons.append(DimComparison(
            dim, _DIM_NAMES[dim], pc.weight if pc else 1.0, p_score, l_score, final,
            divergent=(p_score is not None and l_score is not None
                       and abs(p_score - l_score) >= DIVERGENCE_THRESHOLD),
        ))

    for dim in LLM_ONLY_DIMS:
        report.comparisons.append(DimComparison(
            dim, _DIM_NAMES[dim], _LLM_ONLY_WEIGHT, None, llm.scores[dim], llm.scores[dim],
        ))

    for dim in ("resources", "overhead", "constraints"):
        pc = pattern_by_id.get(dim)
        if pc:
            report.comparisons.append(DimComparison(
                dim, _DIM_NAMES[dim], pc.weight, pc.score, None, pc.score,
            ))

    return report


def render_final_markdown(report: FinalStaticReport) -> str:
    label = f"{report.skill_id}@{report.version}" if report.version else report.skill_id
    fmt = lambda v: f"{v:.2f}" if v is not None else "—"
    lines = [
        f"# Static Evaluation (Final) — {label}",
        "",
        "## 결론",
        "",
        f"**추정 효율 상승: ≈ {report.est_efficiency_uplift:+.0%}** (정적 합성 추정 — 실측 아님)",
        f"(패턴 채점 + LLM 판정({report.llm.model if report.llm else '?'}) 합성 점수 "
        f"{report.total_score}/100 × 앵커; 앵커 = SkillsBench 선별 스킬 평균 효과)",
        "",
        "## 패턴 vs LLM 비교",
        "",
        "| 항목 | 가중치 | 패턴 | LLM | 최종 | 비고 |",
        "|---|---|---|---|---|---|",
    ]
    for c in report.comparisons:
        note = "⚠ 괴리" if c.divergent else ""
        lines.append(
            f"| {c.name} | {c.weight:g} | {fmt(c.pattern_score)} | {fmt(c.llm_score)} | {c.final_score:.2f} | {note} |"
        )
    if report.divergences:
        lines += ["", "### 괴리 항목 (패턴↔LLM 차이 ≥ 0.4 — 패턴 오탐/미탐 또는 LLM 오판 후보)", ""]
        for c in report.divergences:
            rationale = (report.llm.rationales.get(c.dim, "") if report.llm else "")[:200]
            lines.append(f"- **{c.name}**: 패턴 {fmt(c.pattern_score)} vs LLM {fmt(c.llm_score)} — LLM 근거: {rationale}")
    if report.llm and report.llm.top_risks:
        lines += ["", "## LLM이 본 주요 위험", ""]
        lines += [f"- {r}" for r in report.llm.top_risks]
    lines += [
        "",
        "> 정적 합성 추정이다: 패턴은 결정적이지만 표면만 보고, LLM은 의미를 읽지만 비결정적이다.",
        "> 두 방식이 갈린 항목은 사람이 확인하라. 실제 효과는 실측(run/batch)으로만 확정된다.",
    ]
    return "\n".join(lines)
