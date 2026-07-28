"""태스크 단위 짝지은 부트스트랩 신뢰구간 (PLAN.md §16)."""
from __future__ import annotations

import random


def paired_bootstrap_ci(
    per_task_diffs: list[float],
    n_boot: int = 10_000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float, float]:
    """(mean_diff, ci_low, ci_high) 반환.

    per_task_diffs: 태스크별 성공률 차이 (조건B 성공률 - 조건A 성공률).
    태스크 단위로 재표집해 짝 구조를 보존한다.
    """
    if not per_task_diffs:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    n = len(per_task_diffs)
    mean = sum(per_task_diffs) / n
    boot_means = sorted(
        sum(rng.choice(per_task_diffs) for _ in range(n)) / n for _ in range(n_boot)
    )
    lo = boot_means[int((alpha / 2) * n_boot)]
    hi = boot_means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return mean, lo, hi
