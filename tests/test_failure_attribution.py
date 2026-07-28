from skill_eval.analyzers.failure import attribute_failure
from skill_eval.models import RunResult, TrajectoryEvent


def _run(**kw) -> RunResult:
    base = dict(
        run_id="r1", experiment_id="e1", condition="C1_FORCED_SKILL",
        task_id="t1", skill_id="s1", skill_version="1.0.0",
        model="m", repeat_index=0,
    )
    base.update(kw)
    return RunResult(**base)


def test_verifier_defect():
    ft, _ = attribute_failure(_run(verifier_error="exit 2"))
    assert ft == "VERIFIER_OR_TASK_DEFECT"


def test_tool_failure():
    r = _run(trajectory=[TrajectoryEvent(0, "error", "bash", "permission denied")])
    ft, _ = attribute_failure(r)
    assert ft == "TOOL_FAILURE"


def test_noncompliance():
    r = _run(skill_was_loaded=True, constraint_verdicts={"C-001": "COVERED_FAIL"})
    ft, _ = attribute_failure(r)
    assert ft == "INSTRUCTION_NONCOMPLIANCE"


def test_skill_defect():
    r = _run(skill_was_loaded=True, constraint_verdicts={"C-001": "COVERED_PASS"})
    ft, _ = attribute_failure(r)
    assert ft == "SKILL_DEFECT"


def test_model_capability():
    ft, _ = attribute_failure(_run(condition="C0_NO_SKILL"))
    assert ft == "MODEL_CAPABILITY_FAILURE"
