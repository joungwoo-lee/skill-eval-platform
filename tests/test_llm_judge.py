import json
from pathlib import Path

import pytest

from skill_eval.analyzers.llm_judge import (
    LLM_ONLY_DIMS, RUBRIC, judge_skill_llm, parse_judge_json,
)
from skill_eval.analyzers.static_final import combine_static, render_final_markdown
from skill_eval.analyzers.static_lint import lint_skill
from skill_eval.registry import SkillPackage

ROOT = Path(__file__).resolve().parents[1]

_GOOD_SCORES = {dim: 0.9 for dim in RUBRIC}


def _fake_runner(scores=None, wrap=""):
    payload = json.dumps({
        "scores": scores or _GOOD_SCORES,
        "rationales": {dim: f"reason {dim}" for dim in RUBRIC},
        "top_risks": ["risk1", "risk2"],
    })
    def runner(prompt, model, claude_bin, timeout):
        assert "SKILL.md 전문" in prompt  # 프롬프트에 스킬 본문 포함 확인
        return f"{wrap}{payload}{wrap[::-1]}"
    return runner


@pytest.fixture()
def skill():
    return SkillPackage.load(ROOT / "skills" / "demo-report" / "1.0.0")


def test_judge_with_fake_runner(skill):
    result = judge_skill_llm(skill, runner=_fake_runner())
    assert set(result.scores) == set(RUBRIC)
    assert all(0.0 <= v <= 1.0 for v in result.scores.values())
    assert result.top_risks == ["risk1", "risk2"]


def test_judge_parses_json_inside_prose(skill):
    result = judge_skill_llm(skill, runner=_fake_runner(wrap="답변입니다:\n```json\n"))
    assert set(result.scores) == set(RUBRIC)


def test_judge_missing_dimension_raises(skill):
    partial = {k: 0.5 for k in list(RUBRIC)[:3]}
    with pytest.raises(ValueError, match="missing dimensions"):
        judge_skill_llm(skill, runner=_fake_runner(scores=partial))


def test_parse_judge_json_no_json():
    with pytest.raises(ValueError):
        parse_judge_json("정량 평가가 어렵습니다")


def test_combine_static_structure(skill):
    pattern = lint_skill(skill)
    llm = judge_skill_llm(skill, runner=_fake_runner())
    final = combine_static(pattern, llm)

    dims = {c.dim for c in final.comparisons}
    # 공유 6 + LLM 전용 3 + 패턴 전용 3 = 12항목
    assert len(final.comparisons) == 12
    assert set(LLM_ONLY_DIMS) <= dims and {"resources", "overhead", "constraints"} <= dims
    assert 0 <= final.total_score <= 100
    assert 0 <= final.est_efficiency_uplift <= 0.49

    # 공유 항목 최종 = 패턴·LLM 평균
    shared = next(c for c in final.comparisons if c.dim == "verification")
    assert shared.final_score == pytest.approx((shared.pattern_score + shared.llm_score) / 2)


def test_combine_flags_divergence(skill):
    pattern = lint_skill(skill)  # demo-report: verification 패턴 점수 1.0
    low = dict(_GOOD_SCORES)
    low["verification"] = 0.1  # LLM은 낮게 → |1.0-0.1| ≥ 0.4 괴리
    llm = judge_skill_llm(skill, runner=_fake_runner(scores=low))
    final = combine_static(pattern, llm)
    assert any(c.dim == "verification" and c.divergent for c in final.comparisons)
    md = render_final_markdown(final)
    assert "괴리" in md


def test_result_from_payload_self_judge():
    from skill_eval.analyzers.llm_judge import result_from_payload

    r = result_from_payload({"scores": _GOOD_SCORES, "model": "claude-fable-5"})
    assert r.model == "claude-fable-5"
    assert set(r.scores) == set(RUBRIC)
    with pytest.raises(ValueError, match="missing dimensions"):
        result_from_payload({"scores": {"trigger": 1.0}})


def test_cli_judge_file_single(tmp_path):
    from skill_eval.cli import main

    judge = tmp_path / "judge.json"
    judge.write_text(json.dumps({"scores": _GOOD_SCORES, "model": "self"}), encoding="utf-8")
    out = tmp_path / "final.md"
    rc = main([
        "lint",
        "--skill", str(ROOT / "skills" / "demo-report" / "1.0.0"),
        "--judge-file", str(judge),
        "--out", str(out),
    ])
    assert rc == 0
    md = out.read_text(encoding="utf-8")
    assert "패턴 vs LLM 비교" in md and "추정 효율 상승" in md


def test_cli_judge_file_mapping(tmp_path):
    from skill_eval.cli import main

    judge = tmp_path / "judge.json"
    judge.write_text(
        json.dumps({"demo-report": {"scores": _GOOD_SCORES, "model": "self"}}),
        encoding="utf-8",
    )
    out = tmp_path / "final.md"
    rc = main([
        "lint",
        "--skill", str(ROOT / "skills" / "demo-report" / "1.0.0"),
        "--judge-file", str(judge),
        "--out", str(out),
    ])
    assert rc == 0
    assert "패턴 vs LLM 비교" in out.read_text(encoding="utf-8")


def test_final_markdown_headline(skill):
    pattern = lint_skill(skill)
    llm = judge_skill_llm(skill, runner=_fake_runner())
    md = render_final_markdown(combine_static(pattern, llm))
    assert "추정 효율 상승" in md and "실측 아님" in md
    assert "패턴 vs LLM 비교" in md
    assert md.index("결론") < md.index("패턴 vs LLM 비교")
