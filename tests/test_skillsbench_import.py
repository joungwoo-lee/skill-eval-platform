"""SkillsBench 임포터 검증. upstream 서브모듈이 초기화된 환경에서만 실행."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from skill_eval.importers.skillsbench import import_sb_task, list_sb_tasks, parse_sb_task_md
from skill_eval.registry import TaskPackage

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream" / "skillsbench"
CITATION = UPSTREAM / "tasks" / "citation-check"

pytestmark = pytest.mark.skipif(
    not CITATION.exists(), reason="upstream submodule not initialized"
)


def test_list_sb_tasks():
    tasks = list_sb_tasks(UPSTREAM)
    assert len(tasks) >= 80  # 공개 릴리스 87개
    assert any(t.name == "citation-check" for t in tasks)


def test_parse_frontmatter():
    fm, body = parse_sb_task_md(CITATION / "task.md")
    assert fm["schema_version"] == "1.3"
    assert "fake" in body.lower()
    assert not body.startswith("---")


def test_import_citation_check(tmp_path):
    dest = import_sb_task(CITATION, dest_root=tmp_path)
    task = TaskPackage.load(dest)
    assert task.task_id == "citation-check"
    assert task.metadata["source"] == "skillsbench"
    assert task.metadata["requires"]["network"] == "public"
    assert (dest / "environment" / "initial_state" / "test.bib").exists()
    assert not (dest / "environment" / "initial_state" / "Dockerfile").exists()
    # 동봉 스킬은 initial_state에서 제외 (C0 오염 방지), 메타데이터에만 기록
    assert not (dest / "environment" / "initial_state" / "skills").exists()
    assert task.metadata["skillsbench"]["bundled_skills"] == ["citation-management"]
    assert (dest / "verifier" / "sb" / "test_outputs.py").exists()
    assert task.verifier_script.exists()
    assert (dest / "oracle" / "solve.sh").exists()


def test_imported_verifier_scores_locally(tmp_path):
    """어댑터 verifier가 로컬에서 실제로 채점하는지: 빈 workdir=0, 정답=1."""
    dest = import_sb_task(CITATION, dest_root=tmp_path / "reg")
    task = TaskPackage.load(dest)
    workdir = tmp_path / "work"
    workdir.mkdir()

    def run_verifier():
        proc = subprocess.run(
            [sys.executable, str(task.verifier_script), str(workdir)],
            capture_output=True, text=True, timeout=600,
        )
        return json.loads(proc.stdout.strip().splitlines()[-1])

    assert run_verifier()["score"] == 0.0  # 산출물 없음 → 실패

    # 원본 pytest에서 기대 정답 추출해 answer.json 작성 → 통과해야 함
    test_src = (dest / "verifier" / "sb" / "test_outputs.py").read_text(encoding="utf-8")
    m = re.search(r"EXPECTED_FAKE_CITATIONS\s*=\s*(\[.*?\])", test_src, re.DOTALL)
    assert m, "expected answer list not found in upstream test"
    expected = eval(m.group(1))  # 리터럴 리스트
    (workdir / "answer.json").write_text(
        json.dumps({"fake_citations": sorted(expected)}), encoding="utf-8"
    )
    assert run_verifier()["score"] == 1.0
