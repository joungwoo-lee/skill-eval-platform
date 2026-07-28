"""Claude Code headless 어댑터 (PLAN.md §15 adapters/claude_code.py).

`claude -p` 비대화 모드로 태스크를 실행한다.
- C1 Forced Skill: 스킬 SKILL.md를 프롬프트에 직접 주입.
- C2 Auto Discovery: workdir/.claude/skills/ 에 스킬 풀을 복사해 에이전트가 스스로 찾게 한다.
- 토큰·비용: `--output-format json` 결과의 usage/cost 필드에서 수집.

주의: 실 LLM 호출이므로 비용이 발생한다. 파이프라인 검증은 MockAdapter로 먼저 한다.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from ..models import TrajectoryEvent
from ..registry import SkillPackage, TaskPackage
from .base import AdapterOutcome, AgentAdapter


class ClaudeCodeAdapter(AgentAdapter):
    name = "claude-code"

    def __init__(self, model: str = "claude-sonnet-5", claude_bin: str = "claude",
                 timeout_seconds: int = 1800):
        self.model = model
        self.claude_bin = claude_bin
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        task: TaskPackage,
        workdir: Path,
        forced_skill: SkillPackage | None = None,
        skill_pool: list[SkillPackage] | None = None,
        seed: int = 0,
    ) -> AdapterOutcome:
        out = AdapterOutcome()
        prompt = task.task_md

        if forced_skill is not None:
            prompt = (
                f"다음 스킬 지침을 반드시 따르라.\n\n---\n{forced_skill.skill_md}\n---\n\n"
                f"업무:\n{prompt}"
            )
            out.skill_was_loaded = True
            out.chosen_skill_id = forced_skill.skill_id
            out.trajectory.append(
                TrajectoryEvent(time.time(), "skill_loaded", "", forced_skill.skill_id)
            )
        elif skill_pool:
            skills_dir = workdir / ".claude" / "skills"
            for s in skill_pool:
                dst = skills_dir / s.skill_id
                dst.mkdir(parents=True, exist_ok=True)
                (dst / "SKILL.md").write_text(s.skill_md, encoding="utf-8")
                for sub in ("scripts", "references", "assets"):
                    src = s.root / sub
                    if src.exists():
                        shutil.copytree(src, dst / sub, dirs_exist_ok=True)

        cmd = [
            self.claude_bin, "-p", prompt,
            "--model", self.model,
            "--output-format", "json",
            "--dangerously-skip-permissions",
        ]
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd, cwd=str(workdir), capture_output=True, text=True,
                timeout=self.timeout_seconds, encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired:
            out.error = f"timeout after {self.timeout_seconds}s"
            out.trajectory.append(TrajectoryEvent(time.time(), "error", "", out.error))
            return out

        out.trajectory.append(
            TrajectoryEvent(t0, "model_call", "claude-code", f"exit={proc.returncode}")
        )
        if proc.returncode != 0:
            out.error = proc.stderr[:1000]
            out.trajectory.append(TrajectoryEvent(time.time(), "error", "", out.error))
            return out

        try:
            result = json.loads(proc.stdout)
            usage = result.get("usage", {})
            out.tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
            out.cost = float(result.get("total_cost_usd", 0.0))
            # C2에서 스킬 사용 여부: 결과 텍스트에 스킬 로드 흔적 탐지
            text = json.dumps(result, ensure_ascii=False)
            if skill_pool:
                for s in skill_pool:
                    if s.skill_id in text:
                        out.skill_was_loaded = True
                        out.chosen_skill_id = s.skill_id
                        out.trajectory.append(
                            TrajectoryEvent(time.time(), "skill_loaded", "", s.skill_id)
                        )
                        break
        except (json.JSONDecodeError, ValueError):
            out.trajectory.append(
                TrajectoryEvent(time.time(), "note", "", "non-json output; usage unavailable")
            )
        return out
