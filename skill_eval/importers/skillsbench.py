"""SkillsBench 태스크 임포터 (계획서 §3.1·§21 — SkillsBench를 실행 기반으로 재사용).

upstream/skillsbench/tasks/<id>/ (schema 1.3: task.md YAML frontmatter +
environment/Dockerfile + oracle/ + verifier/test.sh·pytest) 를
우리 태스크 레지스트리 포맷(tasks/skillsbench/<id>/)으로 변환한다.

변환 규칙:
- task.md: frontmatter 제거한 본문만 (에이전트 지시문)
- metadata.yaml: 우리 스키마로 매핑 + 원본 메타데이터를 `skillsbench:` 아래 보존
- environment/* (Dockerfile 제외) → environment/initial_state/
- verifier/* → verifier/sb/ 원본 보존 + verifier/score.py 어댑터 생성:
  pytest 파일의 `/root` 절대경로를 실행 시점 workdir로 재작성해 로컬 실행,
  통과 여부 → {"score": 1.0|0.0} (SkillsBench의 reward.txt 0/1 방식과 동일)
- oracle/ → 원본 그대로 (solve.sh는 bash용 — Windows 로컬은 참고용)
- sandbox 요구(네트워크/OS/Docker)는 metadata의 `requires:`에 기록 —
  네트워크 필요 태스크는 로컬 실행 시 실패할 수 있으므로 러너가 판단할 근거
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

# verifier/score.py 어댑터 템플릿. workdir 인자를 받아 sb/ pytest를 경로 재작성 후 실행.
_SCORE_SHIM = '''"""SkillsBench verifier 어댑터 (자동 생성).

원본 pytest(sb/)의 /root 절대경로를 workdir로 재작성해 로컬 실행하고,
SkillsBench reward 방식(전체 통과=1, 아니면 0)으로 {"score": ...}를 출력한다.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    workdir = Path(sys.argv[1]).resolve()
    sb_dir = Path(__file__).parent / "sb"
    with tempfile.TemporaryDirectory(prefix="sbverify-") as td:
        tmp = Path(td)
        for f in sb_dir.iterdir():
            if f.suffix == ".py":
                text = f.read_text(encoding="utf-8", errors="replace")
                text = text.replace("/root", workdir.as_posix())
                (tmp / f.name).write_text(text, encoding="utf-8")
            elif f.is_file() and f.name != "test.sh":
                shutil.copy2(f, tmp / f.name)
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(tmp)],
            capture_output=True, text=True, timeout=600, cwd=str(workdir),
        )
    passed = proc.returncode == 0
    print(json.dumps({"score": 1.0 if passed else 0.0,
                      "pytest_exit": proc.returncode,
                      "tail": proc.stdout[-400:]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def _summarize_body(body: str, limit: int = 180) -> str:
    """task.md 본문에서 한줄 요약 추출: 첫 실질 문단을 평문화해 자름."""
    for para in body.split("\n\n"):
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", para)   # 링크 → 라벨
        text = re.sub(r"[#>*`_]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) >= 20:
            if len(text) > limit:
                return text[:limit].rsplit(" ", 1)[0] + "…"
            return text
    return ""


def build_sb_index(upstream_dir: str | Path) -> list[dict]:
    """동봉 태스크 전수 스캔 → 스킬 적합성 검토용 인덱스.

    항목: task_id, 분류(category/subcategory), 난이도, 태그, 네트워크 요구,
    동봉 스킬 목록, 한줄 요약. 스킬 평가 요청 시 이 인덱스를 훑어
    재사용 가능한 태스크가 있는지 판단하는 근거로 쓴다.
    """
    index: list[dict] = []
    for task_dir in list_sb_tasks(upstream_dir):
        fm, body = parse_sb_task_md(task_dir / "task.md")
        meta = fm.get("metadata") or {}
        sandbox = fm.get("sandbox") or {}
        skills_dir = task_dir / "environment" / "skills"
        bundled = (
            sorted(d.name for d in skills_dir.iterdir() if (d / "SKILL.md").exists())
            if skills_dir.exists() else []
        )
        index.append({
            "task_id": task_dir.name,
            "category": meta.get("category"),
            "subcategory": meta.get("subcategory"),
            "difficulty": meta.get("difficulty"),
            "tags": meta.get("tags") or [],
            "network": sandbox.get("network_mode", "none"),
            "bundled_skills": bundled,
            "summary": _summarize_body(body),
        })
    return index


def render_sb_index_markdown(index: list[dict]) -> str:
    lines = [
        "# SkillsBench 동봉 태스크 인덱스",
        "",
        f"총 {len(index)}개. 스킬 평가 시 재사용 후보 검토용 — 기계용 원본은 `sb-task-index.json`.",
        "`network`가 none이 아닌 태스크는 풀이에 외부 접근이 필요해 채점 안정성 주의.",
        "",
        "| task_id | 분류 | 난이도 | network | 한줄 요약 |",
        "|---|---|---|---|---|",
    ]
    for e in index:
        cat = e["category"] or "-"
        if e["subcategory"]:
            cat += f" / {e['subcategory']}"
        lines.append(
            f"| {e['task_id']} | {cat} | {e['difficulty'] or '-'} | {e['network']} | {e['summary']} |"
        )
    return "\n".join(lines) + "\n"


def list_sb_tasks(upstream_dir: str | Path) -> list[Path]:
    tasks_dir = Path(upstream_dir) / "tasks"
    if not tasks_dir.exists():
        return []
    return sorted(p for p in tasks_dir.iterdir() if (p / "task.md").exists())


def parse_sb_task_md(task_md_path: Path) -> tuple[dict, str]:
    raw = task_md_path.read_text(encoding="utf-8", errors="replace")
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw
    return yaml.safe_load(m.group(1)) or {}, raw[m.end():].strip() + "\n"


def import_sb_task(sb_task_dir: str | Path, dest_root: str | Path = "tasks/skillsbench",
                   required_skill: str | None = None) -> Path:
    """SkillsBench 태스크 1개 변환. 반환: 생성된 태스크 디렉토리."""
    src = Path(sb_task_dir)
    task_id = src.name
    fm, body = parse_sb_task_md(src / "task.md")
    meta = fm.get("metadata", {}) or {}
    sandbox = fm.get("sandbox", {}) or {}
    agent_cfg = fm.get("agent", {}) or {}

    dest = Path(dest_root) / task_id
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    (dest / "task.md").write_text(body, encoding="utf-8")

    metadata = {
        "task_id": task_id,
        "domain": "skillsbench",
        "task_type": (meta.get("task_type") or ["unknown"])[0]
        if isinstance(meta.get("task_type"), list) else meta.get("task_type", "unknown"),
        "source": "skillsbench",
        "required_skill": required_skill,
        "requires": {
            "network": sandbox.get("network_mode", "none"),
            "os": sandbox.get("os", "linux"),
            "docker_recommended": True,
        },
        "limits": {
            "wall_clock_seconds": int(agent_cfg.get("timeout_sec", 900)),
        },
        "success": {"verifier": "verifier/score.py", "minimum_score": 1.0},
        "skillsbench": {
            "schema_version": fm.get("schema_version"),
            "category": meta.get("category"),
            "difficulty": meta.get("difficulty"),
            "tags": meta.get("tags"),
        },
    }
    (dest / "metadata.yaml").write_text(
        yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    # environment/skills/ = 태스크에 동봉된 전용 스킬 — initial_state에 복사하면
    # C0(스킬 없음) 조건에 스킬이 새어 들어가 비교가 오염되므로 반드시 제외.
    init_dir = dest / "environment" / "initial_state"
    init_dir.mkdir(parents=True)
    src_env = src / "environment"
    bundled_skills: list[str] = []
    if src_env.exists():
        for f in src_env.iterdir():
            if f.name == "Dockerfile":
                continue
            if f.name == "skills" and f.is_dir():
                bundled_skills = sorted(d.name for d in f.iterdir() if (d / "SKILL.md").exists())
                continue
            if f.is_dir():
                shutil.copytree(f, init_dir / f.name)
            else:
                shutil.copy2(f, init_dir / f.name)
    if bundled_skills:
        metadata["skillsbench"]["bundled_skills"] = bundled_skills
        (dest / "metadata.yaml").write_text(
            yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    verifier_dir = dest / "verifier"
    if (src / "verifier").exists():
        shutil.copytree(src / "verifier", verifier_dir / "sb")
    else:
        (verifier_dir / "sb").mkdir(parents=True)
    (verifier_dir / "score.py").write_text(_SCORE_SHIM, encoding="utf-8")

    if (src / "oracle").exists():
        shutil.copytree(src / "oracle", dest / "oracle")

    return dest
