"""Statistical utilities for audit-grade evaluation.

Functions here are intentionally simple and transparent, favouring
reproducibility and auditability over raw performance.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence


def _as_list_floats(values: Iterable[float]) -> List[float]:
    xs = [float(v) for v in values]
    if not xs:
        raise ValueError("values must be a non-empty sequence")
    return xs


def bootstrap_ci(
    values: Sequence[float],
    metric_fn: Callable[[Sequence[float]], float],
    n_boot: int = 2000,
    seed: int = 42,
    ci: float = 0.95,
) -> dict:
    """Simple percentile bootstrap confidence interval.

    Parameters
    ----------
    values:
        1D list/sequence of scalar values.
    metric_fn:
        Function mapping a sequence of values to a scalar metric
        (e.g. mean, accuracy). It is applied to the original values
        to obtain the point estimate, and to each bootstrap sample.
    n_boot:
        Number of bootstrap resamples (default 2000).
    seed:
        Random seed for resampling; fixes reproducibility.
    ci:
        Confidence level in (0,1), e.g. 0.95.

    Returns
    -------
    dict
        {
          "point": float,
          "ci_low": float,
          "ci_high": float,
          "n": int,
          "n_boot": int,
          "seed": int,
          "ci": float,
        }
    """
    xs = _as_list_floats(values)
    if not (0.0 < ci < 1.0):
        raise ValueError(f"ci must be in (0,1), got {ci}")
    if n_boot <= 0:
        raise ValueError(f"n_boot must be > 0, got {n_boot}")

    rng = random.Random(seed)
    n = len(xs)

    point = float(metric_fn(xs))

    boot_stats: List[float] = []
    for _ in range(n_boot):
        sample = [xs[rng.randrange(n)] for _ in range(n)]
        boot_stats.append(float(metric_fn(sample)))

    boot_stats.sort()
    alpha = (1.0 - ci) / 2.0
    low_idx = max(0, int(alpha * n_boot))
    high_idx = min(n_boot - 1, int((1.0 - alpha) * n_boot) - 1)

    ci_low = boot_stats[low_idx]
    ci_high = boot_stats[high_idx]

    return {
        "point": point,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "n": n,
        "n_boot": n_boot,
        "seed": seed,
        "ci": ci,
    }


def paired_bootstrap_delta(
    a_values: Sequence[float],
    b_values: Sequence[float],
    metric_fn: Callable[[Sequence[float]], float],
    n_boot: int = 2000,
    seed: int = 42,
    ci: float = 0.95,
) -> dict:
    """Paired percentile bootstrap for metric differences.

    Interprets (a_values[i], b_values[i]) as a paired measurement
    for system A and B on the same example.
    """
    a = _as_list_floats(a_values)
    b = _as_list_floats(b_values)
    if len(a) != len(b):
        raise ValueError(f"a_values and b_values must have same length, got {len(a)} and {len(b)}")
    if not (0.0 < ci < 1.0):
        raise ValueError(f"ci must be in (0,1), got {ci}")
    if n_boot <= 0:
        raise ValueError(f"n_boot must be > 0, got {n_boot}")

    rng = random.Random(seed)
    n = len(a)

    point_a = float(metric_fn(a))
    point_b = float(metric_fn(b))
    delta_point = point_b - point_a

    boot_deltas: List[float] = []
    for _ in range(n_boot):
        # Paired resampling: resample indices jointly
        indices = [rng.randrange(n) for _ in range(n)]
        a_s = [a[i] for i in indices]
        b_s = [b[i] for i in indices]
        boot_deltas.append(float(metric_fn(b_s) - metric_fn(a_s)))

    boot_deltas.sort()
    alpha = (1.0 - ci) / 2.0
    low_idx = max(0, int(alpha * n_boot))
    high_idx = min(n_boot - 1, int((1.0 - alpha) * n_boot) - 1)

    ci_low = boot_deltas[low_idx]
    ci_high = boot_deltas[high_idx]

    return {
        "delta_point": delta_point,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "n": n,
        "n_boot": n_boot,
        "seed": seed,
        "ci": ci,
    }


def mcnemar_test(y_a: Sequence[int], y_b: Sequence[int]) -> dict:
    """Classic McNemar test for paired 0/1 outcomes.

    Parameters
    ----------
    y_a, y_b:
        Binary 0/1 outcomes for two systems A and B on the *same*
        set of examples. Both sequences must have identical length.

    Implementation notes
    --------------------
    - We treat:
        b = # {A correct (=1), B incorrect (=0)}
        c = # {A incorrect (=0), B correct (=1)}
      These are the "discordant" pairs.
    - The test is implemented using an **exact binomial test**
      with null hypothesis p(b) = p(c) = 0.5, i.e. both systems
      have the same error rate.
    - The p-value is the two-sided exact p-value:
        p = sum_{k: P(K=k) <= P(K=obs)} P(K=k),
      where K ~ Binomial(n=b+c, p=0.5).

    Returns
    -------
    dict
        {
          "b": int,
          "c": int,
          "n": int,              # total pairs
          "n_discordant": int,   # b + c
          "stat": float,         # |b - c|
          "p_value": float,      # in [0,1]
          "method": str,         # "exact_binomial"
          "warning": str | None,
        }
    """
    a = [1 if int(v) != 0 else 0 for v in y_a]
    b_vals = [1 if int(v) != 0 else 0 for v in y_b]
    if len(a) != len(b_vals):
        raise ValueError(f"y_a and y_b must have same length, got {len(a)} and {len(b_vals)}")
    n = len(a)
    if n == 0:
        raise ValueError("y_a and y_b must be non-empty")

    b = 0  # A=1, B=0
    c = 0  # A=0, B=1
    for ya, yb in zip(a, b_vals):
        if ya == 1 and yb == 0:
            b += 1
        elif ya == 0 and yb == 1:
            c += 1

    n_disc = b + c
    stat = float(abs(b - c))

    warning = None
    if n_disc == 0:
        # No discordant pairs: tests are undefined; report p=1.
        warning = "McNemar test undefined when b+c=0 (no discordant pairs); returning p_value=1.0"
        return {
            "b": b,
            "c": c,
            "n": n,
            "n_discordant": n_disc,
            "stat": stat,
            "p_value": 1.0,
            "method": "exact_binomial",
            "warning": warning,
        }

    # Exact binomial test under H0: p = 0.5
    k_obs = min(b, c)
    p_obs = _binom_pmf(k_obs, n_disc)
    p_value = 0.0
    for k in range(0, n_disc + 1):
        pk = _binom_pmf(k, n_disc)
        if pk <= p_obs + 1e-15:  # numerical tolerance
            p_value += pk

    if n_disc < 25:
        extra = f" (small-sample regime, n_discordant={n_disc})"
        if warning is None:
            warning = "Using exact binomial McNemar test" + extra
        else:
            warning += " | Using exact binomial McNemar test" + extra

    return {
        "b": b,
        "c": c,
        "n": n,
        "n_discordant": n_disc,
        "stat": stat,
        "p_value": min(1.0, max(0.0, p_value)),
        "method": "exact_binomial",
        "warning": warning,
    }


def _binom_pmf(k: int, n: int) -> float:
    """Binomial(n, 0.5) probability mass at k."""
    if k < 0 or k > n:
        return 0.0
    # P(K=k) = C(n,k) * 0.5**n
    return math.comb(n, k) / float(2**n)

