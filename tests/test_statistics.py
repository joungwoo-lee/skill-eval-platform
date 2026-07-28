from skill_eval.statistics.mcnemar import mcnemar_exact, paired_success_table
from skill_eval.statistics.paired_bootstrap import paired_bootstrap_ci


def test_mcnemar_no_discordant():
    assert mcnemar_exact(0, 0) == 1.0


def test_mcnemar_symmetric_is_insignificant():
    assert mcnemar_exact(5, 5) > 0.5


def test_mcnemar_strong_asymmetry_is_significant():
    assert mcnemar_exact(0, 15) < 0.001


def test_mcnemar_bounds():
    for b, c in [(0, 1), (3, 7), (10, 10), (2, 0)]:
        p = mcnemar_exact(b, c)
        assert 0.0 <= p <= 1.0


def test_paired_success_table():
    a = [True, True, False, False]
    b = [True, False, True, False]
    assert paired_success_table(a, b) == (1, 1, 1, 1)


def test_bootstrap_ci_contains_mean():
    diffs = [0.2, 0.4, 0.0, 0.6, 0.2, 0.4, 0.2]
    mean, lo, hi = paired_bootstrap_ci(diffs, n_boot=2000, seed=1)
    assert lo <= mean <= hi
    assert abs(mean - sum(diffs) / len(diffs)) < 1e-9


def test_bootstrap_empty():
    assert paired_bootstrap_ci([]) == (0.0, 0.0, 0.0)
