"""Skill Coverage 판정 (PLAN.md §11).

constraints.json 규격 (스킬 패키지에 동봉):
[
  {
    "constraint_id": "C-001",
    "condition": "...사람이 읽는 조건...",
    "condition_pattern": "정규식 — 궤적에서 조건 발생 여부",
    "required_pattern": "정규식 — 준수 증거",
    "forbidden_pattern": "정규식 — 위반 증거 (선택)",
    "severity": "high|medium|low"
  }
]

판정 (§11.2):
- condition_pattern 미매칭 → NOT_APPLICABLE
- forbidden_pattern 매칭 → COVERED_FAIL
- required_pattern 매칭 → COVERED_PASS
- 조건은 발생했으나 증거 규칙이 없거나 아무 것도 매칭 안 됨 → 규칙 없으면 UNJUDGEABLE,
  required_pattern이 있는데 미매칭이면 COVERED_FAIL
"""
from __future__ import annotations

import re

from ..models import TrajectoryEvent


def judge_constraints(constraints: list[dict], trajectory: list[TrajectoryEvent]) -> dict[str, str]:
    text = "\n".join(ev.as_text() for ev in trajectory)
    verdicts: dict[str, str] = {}
    for c in constraints:
        cid = c["constraint_id"]
        cond = c.get("condition_pattern")
        if cond and not re.search(cond, text, re.IGNORECASE):
            verdicts[cid] = "NOT_APPLICABLE"
            continue
        forbidden = c.get("forbidden_pattern")
        if forbidden and re.search(forbidden, text, re.IGNORECASE):
            verdicts[cid] = "COVERED_FAIL"
            continue
        required = c.get("required_pattern")
        if required:
            verdicts[cid] = (
                "COVERED_PASS" if re.search(required, text, re.IGNORECASE) else "COVERED_FAIL"
            )
        else:
            verdicts[cid] = "UNJUDGEABLE"
    return verdicts


def compute_coverage(all_verdicts: list[dict[str, str]], total_constraints: int) -> dict:
    """전체 런의 판정을 합산해 커버리지 계산 (§11.3).

    Skill Coverage = 평가 가능한 상태로 실행된 제약 수 / 전체 행동 제약 수
    제약이 어느 런에서든 COVERED_PASS/COVERED_FAIL로 한 번이라도 판정되면 '실행됨'.
    """
    covered: set[str] = set()
    fail_counts: dict[str, int] = {}
    pass_counts: dict[str, int] = {}
    seen: set[str] = set()
    for verdicts in all_verdicts:
        for cid, v in verdicts.items():
            seen.add(cid)
            if v in ("COVERED_PASS", "COVERED_FAIL"):
                covered.add(cid)
            if v == "COVERED_FAIL":
                fail_counts[cid] = fail_counts.get(cid, 0) + 1
            elif v == "COVERED_PASS":
                pass_counts[cid] = pass_counts.get(cid, 0) + 1
    denom = total_constraints or len(seen)
    return {
        "coverage": len(covered) / denom if denom else 0.0,
        "covered_constraints": sorted(covered),
        "unverified_constraints": sorted(seen - covered),
        "fail_counts": fail_counts,
        "pass_counts": pass_counts,
    }
