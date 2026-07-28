"""McNemar 검정 (PLAN.md §16). scipy 없이 정확 이항 검정으로 구현."""
from __future__ import annotations

from math import comb


def mcnemar_exact(b: int, c: int) -> float:
    """불일치 쌍 b(조건A만 성공), c(조건B만 성공)에 대한 양측 정확 p-value.

    귀무가설: 두 조건의 성공 확률이 같다 (불일치 쌍이 반반).
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    # P(X <= k) + P(X >= n-k), X ~ Binomial(n, 0.5); 양측
    tail = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    p = 2 * tail
    if b == c:
        p -= comb(n, k) / (2 ** n)  # 중앙값 이중계산 보정
    return min(1.0, p)


def paired_success_table(a_successes: list[bool], b_successes: list[bool]) -> tuple[int, int, int, int]:
    """짝지은 성공 여부에서 (both, a_only, b_only, neither) 집계."""
    assert len(a_successes) == len(b_successes), "paired lists must be equal length"
    both = a_only = b_only = neither = 0
    for a, b in zip(a_successes, b_successes):
        if a and b:
            both += 1
        elif a:
            a_only += 1
        elif b:
            b_only += 1
        else:
            neither += 1
    return both, a_only, b_only, neither
