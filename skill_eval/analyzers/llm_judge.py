"""LLM 판정 정적 채점 — 언어모델이 SKILL.md를 읽고 루브릭으로 평가한다.

패턴(정규식) 채점의 보완: 표현 방식·언어에 묶이지 않고 의미를 읽으며,
패턴이 원리적으로 못 보는 것(내용 타당성, 내부 모순, 절차 누락)을 본다.
대신 비결정적이고 호출 비용이 있다. 최종 정적 평가는 static_final.combine_static()이
패턴 채점과 비교·합성해 낸다. 스킬 파일은 읽기만 한다.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from typing import Callable

from ..registry import SkillPackage

# 루브릭. shared_* 6개는 패턴 채점(static_lint)과 같은 항목 — 두 방식의 비교 기준.
# llm_only_* 3개는 패턴이 원리적으로 판정 불가한 항목.
RUBRIC: dict[str, str] = {
    # shared (패턴 채점과 1:1 대응)
    "trigger": "발동 조건이 구체적인가 — 언제 이 스킬을 써야 하는지 오발동/미발동 여지 없이 판단 가능한가",
    "steps": "지침이 실행 가능한 단계로 분해되어 있는가 — 순서와 행동이 명확한가",
    "vagueness": "모호한 표현 없이 관측 가능한 행동으로 서술되는가 (구체적일수록 높은 점수)",
    "verification": "결과를 반환하기 전 자체 검증하는 절차가 실효성 있게 정의되어 있는가",
    "recovery": "실패·오류 상황의 대응 지침이 있는가",
    "output_spec": "산출물이 무엇이고 어떤 형식이어야 하는지 명확한가",
    # LLM 전용 (패턴으로 판정 불가)
    "content_validity": "지침 내용이 기술적으로 타당하고 실제로 실행 가능한가 (틀린 명령·존재하지 않는 API·잘못된 절차 없음)",
    "consistency": "지침들 사이에 모순이 없는가",
    "sufficiency": "이 스킬이 표방하는 업무를 완수하는 데 필요한 핵심 절차가 빠짐없이 있는가",
}

LLM_ONLY_DIMS = ("content_validity", "consistency", "sufficiency")
SHARED_DIMS = tuple(d for d in RUBRIC if d not in LLM_ONLY_DIMS)


@dataclass
class LlmJudgeResult:
    scores: dict[str, float]              # dim → 0.0~1.0
    rationales: dict[str, str] = field(default_factory=dict)
    top_risks: list[str] = field(default_factory=list)
    model: str = ""
    raw: str = ""


def _build_prompt(skill: SkillPackage) -> str:
    listing = "\n".join(
        str(p.relative_to(skill.root)) for p in sorted(skill.root.rglob("*")) if p.is_file()
    )
    rubric_lines = "\n".join(f'- "{k}": {v}' for k, v in RUBRIC.items())
    return f"""너는 에이전트 스킬(SKILL.md) 심사관이다. 아래 스킬 문서를 읽고 루브릭 각 항목을 0.0~1.0으로 채점하라.

루브릭:
{rubric_lines}

채점 원칙:
- 문서에 실제로 쓰여 있는 것만 근거로 삼는다. 선의로 보완 해석하지 않는다.
- 각 점수에 한 줄 근거(rationale)를 단다.
- 이 스킬을 실전 투입할 때 가장 큰 위험 최대 3개를 top_risks에 쓴다.
- 출력은 아래 JSON 하나만. 다른 텍스트 금지.

{{"scores": {{"trigger": 0.0, "steps": 0.0, "vagueness": 0.0, "verification": 0.0, "recovery": 0.0, "output_spec": 0.0, "content_validity": 0.0, "consistency": 0.0, "sufficiency": 0.0}}, "rationales": {{"trigger": "...", "...": "..."}}, "top_risks": ["...", "..."]}}

스킬 패키지 파일 목록:
{listing}

SKILL.md 전문:
---
{skill.skill_md}
---"""


def _default_runner(prompt: str, model: str, claude_bin: str, timeout: int) -> str:
    """claude -p headless 실행, 결과 텍스트 반환."""
    proc = subprocess.run(
        [claude_bin, "-p", prompt, "--model", model, "--output-format", "json"],
        capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exit {proc.returncode}: {proc.stderr[:500]}")
    try:
        return json.loads(proc.stdout).get("result", proc.stdout)
    except json.JSONDecodeError:
        return proc.stdout


def parse_judge_json(text: str) -> dict:
    """응답 텍스트에서 JSON 오브젝트 추출 (코드펜스·잡담 내성)."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON object in judge output: {text[:200]}")
    return json.loads(m.group(0))


def judge_skill_llm(
    skill: SkillPackage,
    model: str = "claude-haiku-4-5-20251001",
    claude_bin: str = "claude",
    timeout: int = 300,
    runner: Callable[[str, str, str, int], str] | None = None,
) -> LlmJudgeResult:
    """LLM 판정 1회. runner 주입으로 테스트 가능(실 호출 없이)."""
    text = (runner or _default_runner)(_build_prompt(skill), model, claude_bin, timeout)
    payload = parse_judge_json(text)
    scores_raw = payload.get("scores", {})
    scores = {
        dim: max(0.0, min(1.0, float(scores_raw[dim])))
        for dim in RUBRIC
        if dim in scores_raw
    }
    missing = [d for d in RUBRIC if d not in scores]
    if missing:
        raise ValueError(f"judge output missing dimensions: {missing}")
    return LlmJudgeResult(
        scores=scores,
        rationales={k: str(v) for k, v in payload.get("rationales", {}).items()},
        top_risks=[str(r) for r in payload.get("top_risks", [])][:3],
        model=model,
        raw=text,
    )
