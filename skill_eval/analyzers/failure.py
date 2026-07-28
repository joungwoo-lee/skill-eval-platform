"""실패 원인 자동 분류 (PLAN.md §12).

규칙 기반 1차 분류. 신뢰도가 낮은 케이스는 사람이 검토한다는 원칙에 따라
rationale에 근거를 남긴다.
"""
from __future__ import annotations

from ..models import RunResult


def attribute_failure(run: RunResult) -> tuple[str, str]:
    """(failure_type, rationale) 반환. 성공 런에는 호출하지 않는다."""
    if run.verifier_error:
        return "VERIFIER_OR_TASK_DEFECT", f"verifier error: {run.verifier_error}"

    tool_errors = [ev for ev in run.trajectory if ev.event_type == "error"]
    if tool_errors:
        return "TOOL_FAILURE", f"trajectory errors: {tool_errors[0].detail[:200]}"

    violated = [cid for cid, v in run.constraint_verdicts.items() if v == "COVERED_FAIL"]
    if run.skill_was_loaded and violated:
        return (
            "INSTRUCTION_NONCOMPLIANCE",
            f"skill loaded but constraints violated: {', '.join(violated)}",
        )

    if run.skill_was_loaded and not violated:
        return (
            "SKILL_DEFECT",
            "skill loaded, all judged constraints followed, but task still failed "
            "— instructions likely wrong or incomplete",
        )

    return "MODEL_CAPABILITY_FAILURE", "no skill in play; base model failed the task"
