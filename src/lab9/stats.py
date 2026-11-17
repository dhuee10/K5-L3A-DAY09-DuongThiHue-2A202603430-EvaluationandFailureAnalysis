"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def _is_pos(label: str) -> bool:
    return str(label).strip().upper() == POS


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError(f"human ({len(human)}) and judge ({len(judge)}) differ in length")
    cm = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for h, j in zip(human, judge):
        hp, jp = _is_pos(h), _is_pos(j)
        if hp and jp:
            cm["tp"] += 1
        elif jp:
            cm["fp"] += 1
        elif hp:
            cm["fn"] += 1
        else:
            cm["tn"] += 1
    return cm


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    """precision = tp/(tp+fp), recall = tp/(tp+fn); 0.0 when the denominator is 0."""
    cm = confusion(human, judge)
    p = cm["tp"] / (cm["tp"] + cm["fp"]) if cm["tp"] + cm["fp"] else 0.0
    r = cm["tp"] / (cm["tp"] + cm["fn"]) if cm["tp"] + cm["fn"] else 0.0
    return p, r


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())
    if n == 0:
        raise ValueError("kappa undefined on 0 items")
    p_o = (cm["tp"] + cm["tn"]) / n
    h_pos = (cm["tp"] + cm["fn"]) / n
    j_pos = (cm["tp"] + cm["fp"]) / n
    p_e = h_pos * j_pos + (1 - h_pos) * (1 - j_pos)
    if math.isclose(p_e, 1.0):
        raise ValueError("kappa undefined: expected agreement p_e == 1 (constant labels)")
    return (p_o - p_e) / (1 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1].
    (p_obs + spec - 1) / (sens + spec - 1). Undefined when the judge is no better than chance."""
    denom = sensitivity + specificity - 1
    if denom <= 0:
        raise ValueError(f"Rogan-Gladen undefined: sens + spec - 1 = {denom:.3f} <= 0")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / denom))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    if x.ndim != 1 or x.shape != y.shape or x.size == 0:
        raise ValueError("paired_bootstrap needs two non-empty 1-D sequences of the same length")
    if np.array_equal(x, y):
        return 0.0, 0.0, 0.0
    d = float(x.mean() - y.mean())
    diff = x - y
    if np.all(diff == diff[0]):           # constant difference: every resample gives the same Δ
        return d, d, d

    def stat(u, v, axis=-1):
        return u.mean(axis=axis) - v.mean(axis=axis)

    res = bootstrap((x, y), stat, paired=True, vectorized=True, n_resamples=n_resamples,
                    confidence_level=confidence, method="percentile",
                    rng=np.random.default_rng(rng))
    return d, float(res.confidence_interval.low), float(res.confidence_interval.high)


def _check_nck(n: int, c: int, k: int) -> None:
    for name, v in (("n", n), ("c", c), ("k", k)):
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(f"{name} must be an int, got {v!r}")
    if n < 1 or k < 1 or c < 0 or c > n or k > n:
        raise ValueError(f"need 1 <= k <= n and 0 <= c <= n, got n={n} c={c} k={k}")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _check_nck(n, c, k)
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _check_nck(n, c, k)
    return math.comb(c, k) / math.comb(n, k)
