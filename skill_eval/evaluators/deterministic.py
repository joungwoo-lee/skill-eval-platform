"""결정적 검증기 실행 (PLAN.md §2.3, §9.1).

verifier/score.py 계약:
- 인자: 작업 디렉토리 경로 1개
- stdout 마지막 줄: JSON {"score": float, ...}
- exit 0 이외 또는 JSON 파싱 실패 = 검증기 오류(태스크 결함으로 분류)
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VerifierResult:
    score: float
    success: bool
    error: str = ""
    detail: dict | None = None


def run_verifier(verifier_script: Path, workdir: Path, minimum_score: float = 1.0,
                 timeout: int = 300) -> VerifierResult:
    if not verifier_script.exists():
        return VerifierResult(0.0, False, error=f"verifier not found: {verifier_script}")
    try:
        proc = subprocess.run(
            [sys.executable, str(verifier_script), str(workdir)],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return VerifierResult(0.0, False, error=f"verifier timeout {timeout}s")

    if proc.returncode != 0:
        return VerifierResult(0.0, False, error=f"verifier exit {proc.returncode}: {proc.stderr[:500]}")

    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    if not lines:
        return VerifierResult(0.0, False, error="verifier produced no output")
    try:
        payload = json.loads(lines[-1])
        score = float(payload.get("score", 0.0))
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return VerifierResult(0.0, False, error=f"verifier output parse error: {e}")

    return VerifierResult(score=score, success=score >= minimum_score, detail=payload)
