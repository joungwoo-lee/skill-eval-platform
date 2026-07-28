"""SkillsBench 태스크 인덱스 검증. upstream 서브모듈 필요."""
from pathlib import Path

import pytest

from skill_eval.importers.skillsbench import build_sb_index, render_sb_index_markdown

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream" / "skillsbench"

pytestmark = pytest.mark.skipif(
    not (UPSTREAM / "tasks").exists(), reason="upstream submodule not initialized"
)


def test_build_index_covers_all_tasks():
    index = build_sb_index(UPSTREAM)
    assert len(index) >= 80
    by_id = {e["task_id"]: e for e in index}
    cc = by_id["citation-check"]
    assert cc["network"] == "public"
    assert cc["bundled_skills"] == ["citation-management"]
    assert len(cc["summary"]) > 20  # 한줄 요약이 실제로 뽑혔는지
    # 모든 항목에 요약 존재 (빈 요약은 인덱스로서 무의미)
    empty = [e["task_id"] for e in index if not e["summary"]]
    assert not empty, f"summary missing: {empty}"


def test_render_index_markdown():
    index = build_sb_index(UPSTREAM)
    md = render_sb_index_markdown(index)
    assert "citation-check" in md
    assert md.count("|") > len(index)  # 표 형태


def test_cli_index_sb(tmp_path):
    from skill_eval.cli import main

    out_json = tmp_path / "idx.json"
    out_md = tmp_path / "idx.md"
    rc = main([
        "index-sb", "--upstream", str(UPSTREAM),
        "--out-json", str(out_json), "--out-md", str(out_md),
    ])
    assert rc == 0
    import json
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert len(data) >= 80
    assert out_md.exists()
