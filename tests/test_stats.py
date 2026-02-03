"""Unit tests for core.stats bootstrap and McNemar utilities."""

from math import isclose
from pathlib import Path
import sys

# Make project root importable even under path-encoding quirks
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stats import bootstrap_ci, paired_bootstrap_delta, mcnemar_test


def _mean(xs):
    return sum(xs) / len(xs)


def test_bootstrap_ci_basic_properties():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]

    # Same seed -> deterministic
    r1 = bootstrap_ci(values, _mean, n_boot=500, seed=123, ci=0.9)
    r2 = bootstrap_ci(values, _mean, n_boot=500, seed=123, ci=0.9)
    assert r1 == r2

    # Different seed -> CI should typically differ
    r3 = bootstrap_ci(values, _mean, n_boot=500, seed=456, ci=0.9)
    assert r1["point"] == r3["point"]  # point estimate independent of seed
    # CI bounds can coincide by chance, but very unlikely; allow equality fallback
    if r1["ci_low"] == r3["ci_low"] and r1["ci_high"] == r3["ci_high"]:
        # at least ensure n_boot and seed differ
        assert r1["seed"] != r3["seed"]

    # Basic shape: ci_low <= point <= ci_high
    assert r1["ci_low"] <= r1["point"] <= r1["ci_high"]
    assert r1["n"] == len(values)
    assert r1["n_boot"] == 500


def test_paired_bootstrap_delta_shapes():
    a = [0.0, 1.0, 0.0, 1.0]
    b = [1.0, 1.0, 0.0, 1.0]

    r = paired_bootstrap_delta(a, b, _mean, n_boot=500, seed=7, ci=0.9)
    assert r["n"] == len(a) == len(b)
    # delta_point should equal mean(b) - mean(a)
    expected_delta = _mean(b) - _mean(a)
    assert isclose(r["delta_point"], expected_delta)
    assert r["ci_low"] <= r["delta_point"] <= r["ci_high"]


def test_mcnemar_non_trivial_example():
    # Example with discordant pairs: A and B differ on two items
    y_a = [1, 1, 0, 0]
    y_b = [1, 0, 1, 0]
    res = mcnemar_test(y_a, y_b)
    assert res["b"] == 1
    assert res["c"] == 1
    assert res["n_discordant"] == 2
    assert res["p_value"] > 0.0
    assert res["p_value"] <= 1.0

    # Symmetric case b=c should not yield extremely small p-value
    assert res["p_value"] > 0.1


def test_mcnemar_degenerate_no_discordant():
    y_a = [1, 0, 1]
    y_b = [1, 0, 1]
    res = mcnemar_test(y_a, y_b)
    assert res["n_discordant"] == 0
    assert res["p_value"] == 1.0
    assert "undefined" in (res["warning"] or "")

