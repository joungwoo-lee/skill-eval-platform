from skill_eval.analyzers.coverage import compute_coverage, judge_constraints
from skill_eval.models import TrajectoryEvent

CONSTRAINTS = [
    {
        "constraint_id": "C-001",
        "condition_pattern": "write_file",
        "required_pattern": "run_verifier",
        "forbidden_pattern": "returned without verification",
    },
    {
        "constraint_id": "C-002",
        "condition_pattern": "database",
        "required_pattern": "backup",
    },
    {
        "constraint_id": "C-003",
        "condition_pattern": "write_file",
    },
]


def _ev(event_type, tool="", detail=""):
    return TrajectoryEvent(0.0, event_type, tool, detail)


def test_pass_fail_na_unjudgeable():
    traj = [_ev("tool_call", "write_file", "made report"), _ev("tool_call", "run_verifier", "ok")]
    v = judge_constraints(CONSTRAINTS, traj)
    assert v == {"C-001": "COVERED_PASS", "C-002": "NOT_APPLICABLE", "C-003": "UNJUDGEABLE"}


def test_forbidden_wins():
    traj = [
        _ev("tool_call", "write_file", "made report"),
        _ev("tool_call", "run_verifier", "ok"),
        _ev("note", "", "returned without verification"),
    ]
    v = judge_constraints(CONSTRAINTS, traj)
    assert v["C-001"] == "COVERED_FAIL"


def test_required_missing_is_fail():
    traj = [_ev("tool_call", "write_file", "made report")]
    assert judge_constraints(CONSTRAINTS, traj)["C-001"] == "COVERED_FAIL"


def test_compute_coverage():
    all_verdicts = [
        {"C-001": "COVERED_PASS", "C-002": "NOT_APPLICABLE", "C-003": "UNJUDGEABLE"},
        {"C-001": "COVERED_FAIL", "C-002": "NOT_APPLICABLE", "C-003": "UNJUDGEABLE"},
    ]
    cov = compute_coverage(all_verdicts, total_constraints=3)
    assert abs(cov["coverage"] - 1 / 3) < 1e-9
    assert cov["covered_constraints"] == ["C-001"]
    assert set(cov["unverified_constraints"]) == {"C-002", "C-003"}
    assert cov["fail_counts"] == {"C-001": 1}
