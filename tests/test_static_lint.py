from pathlib import Path

from skill_eval.analyzers.static_lint import lint_skill, render_lint_markdown
from skill_eval.registry import SkillPackage

ROOT = Path(__file__).resolve().parents[1]


def _make_skill(tmp_path: Path, md: str, with_constraints: bool = False) -> SkillPackage:
    root = tmp_path / "my-skill" / "1.0.0"
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text(md, encoding="utf-8")
    if with_constraints:
        (root / "constraints.json").write_text("[]", encoding="utf-8")
    return SkillPackage.load(root)


def test_lint_demo_report_is_decent():
    skill = SkillPackage.load(ROOT / "skills" / "demo-report" / "1.0.0")
    report = lint_skill(skill)
    assert report.total_score >= 60
    by_id = {c.check_id: c for c in report.checks}
    assert by_id["verification"].score == 1.0  # "자체 검증" 지침 있음
    assert by_id["steps"].score > 0
    assert by_id["constraints"].score == 1.0
    assert report.est_tokens > 0


def test_lint_vague_skill_scores_low(tmp_path):
    md = "# bad-skill\n\n잘 처리한다. 상황에 맞게 적절히 알아서 한다. 필요에 따라 유연하게.\n"
    report = lint_skill(_make_skill(tmp_path, md))
    assert report.total_score < 40
    by_id = {c.check_id: c for c in report.checks}
    assert by_id["verification"].score == 0.0
    assert by_id["steps"].score == 0.0
    assert by_id["vagueness"].score < 0.7
    assert report.findings  # 개선 포인트가 나와야 함


def test_lint_detects_broken_resource_reference(tmp_path):
    md = "# s\n\n1. scripts/helper.py 를 실행한다.\n2. 결과 파일을 검증한다.\n"
    report = lint_skill(_make_skill(tmp_path, md))
    by_id = {c.check_id: c for c in report.checks}
    assert by_id["resources"].score == 0.0  # scripts/ 참조하지만 디렉토리 없음
    assert "scripts" in by_id["resources"].evidence


def test_lint_markdown_render(tmp_path):
    skill = SkillPackage.load(ROOT / "skills" / "demo-report" / "1.0.0")
    report = lint_skill(skill)
    md = render_lint_markdown(report)
    assert "추정 효율 상승" in md  # 결론 지표: 효율 상승 %
    assert "실측 아님" in md
    assert "구조 품질 점수" in md
    assert 0 <= report.est_efficiency_uplift <= report.ANCHOR_UPLIFT


_KR_SKILL = """---
name: report-maker
description: 사용자가 "리포트 만들어"라고 하면 호출.
---
# report-maker

1. data.csv 를 읽는다.
2. report.md 를 작성한다 (형식: 제목 + 합계).
3. 결과를 검증한 뒤 반환한다.
4. 실패 시 한 번 재시도한다.
5. 산출물 파일을 저장한다.
"""

_EN_SKILL = """---
name: report-maker
description: Invoke when the user says "make a report".
---
# report-maker

1. Read data.csv.
2. Write report.md (format: title + total).
3. Verify the result before returning.
4. Retry once on failure.
5. Save the output file.
"""


def test_language_parity_kr_en(tmp_path):
    """같은 내용의 한글판/영어판 스킬은 항목별 점수가 같아야 한다."""
    kr = lint_skill(_make_skill(tmp_path / "kr", _KR_SKILL))
    en = lint_skill(_make_skill(tmp_path / "en", _EN_SKILL))
    kr_scores = {c.check_id: c.score for c in kr.checks}
    en_scores = {c.check_id: c.score for c in en.checks}
    assert kr_scores == en_scores, f"KR={kr_scores}\nEN={en_scores}"
    assert kr.total_score == en.total_score


def test_cli_lint(tmp_path):
    from skill_eval.cli import main

    out = tmp_path / "lint.md"
    rc = main([
        "lint",
        "--skill", str(ROOT / "skills" / "demo-report" / "1.0.0"),
        "--out", str(out),
    ])
    assert rc == 0
    assert "구조 품질 점수" in out.read_text(encoding="utf-8")
