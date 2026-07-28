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

    init_dir = dest / "environment" / "initial_state"
    init_dir.mkdir(parents=True)
    src_env = src / "environment"
    if src_env.exists():
        for f in src_env.iterdir():
            if f.name == "Dockerfile":
                continue
            if f.is_dir():
                shutil.copytree(f, init_dir / f.name)
            else:
                shutil.copy2(f, init_dir / f.name)

    verifier_dir = dest / "verifier"
    if (src / "verifier").exists():
        shutil.copytree(src / "verifier", verifier_dir / "sb")
    else:
        (verifier_dir / "sb").mkdir(parents=True)
    (verifier_dir / "score.py").write_text(_SCORE_SHIM, encoding="utf-8")

    if (src / "oracle").exists():
        shutil.copytree(src / "oracle", dest / "oracle")

    return dest
