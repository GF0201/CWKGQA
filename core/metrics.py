"""Two-level metrics structure, validation and save."""
import csv
from pathlib import Path
from typing import Any, Optional


def make_two_level_metrics(
    total: dict,
    executable_or_answerable: dict,
    coverage_upper_bound: Optional[dict] = None,
) -> dict:
    """Build two-level metrics structure."""
    metrics = {
        "total": total,
        "executable_or_answerable": executable_or_answerable,
    }
    if coverage_upper_bound is not None:
        metrics["coverage_upper_bound"] = coverage_upper_bound
    return metrics


def validate_metrics(metrics: dict) -> None:
    """
    Validate two-level metrics invariants.

    - total.n >= executable_or_answerable.n
    - coverage_upper_bound.ratio == executable_or_answerable.n / total.n (within 1e-6)
    - required keys exist: total, executable_or_answerable, coverage_upper_bound
    """
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be a dict")

    for key in ("total", "executable_or_answerable", "coverage_upper_bound"):
        if key not in metrics or not isinstance(metrics[key], dict):
            raise ValueError(f"metrics missing required section '{key}'")

    total = metrics["total"]
    exec_ok = metrics["executable_or_answerable"]
    cov = metrics["coverage_upper_bound"]

    if "n" not in total or "n" not in exec_ok:
        raise ValueError("metrics.total.n and metrics.executable_or_answerable.n are required")

    n_total = float(total["n"])
    n_exec = float(exec_ok["n"])

    if n_total < n_exec:
        raise ValueError(f"total.n ({n_total}) must be >= executable_or_answerable.n ({n_exec})")

    ratio_expected = 0.0 if n_total == 0 else n_exec / n_total
    ratio = float(cov.get("ratio", ratio_expected))
    if abs(ratio - ratio_expected) > 1e-6:
        raise ValueError(
            f"coverage_upper_bound.ratio ({ratio}) "
            f"!= executable_or_answerable.n / total.n ({ratio_expected})"
        )


def save_metrics(metrics: dict, path: Path) -> None:
    """Persist metrics after basic filesystem setup."""
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)


def validate_audit_artifacts(
    metrics: dict,
    per_sample_list: list,
    failures_path: Path,
) -> None:
    """
    Strong validation rules for audit-grade runs:
    - Rule 1: per_sample_results line count == metrics.total.n
    - Rule 2: executable_or_answerable.n == sum(is_executable==True)
    - Rule 3: if any per-sample em/f1 is None, metrics EM/F1 must be null,
              and failures.csv must have corresponding metric_missing rows
    """
    n_total = metrics.get("total", {}).get("n", 0)
    if len(per_sample_list) != n_total:
        raise ValueError(
            f"per_sample_results count ({len(per_sample_list)}) != metrics.total.n ({n_total})"
        )

    n_exec = sum(1 for p in per_sample_list if p.get("is_executable") is True)
    expected_exec = metrics.get("executable_or_answerable", {}).get("n", 0)
    if n_exec != expected_exec:
        raise ValueError(
            f"executable count ({n_exec}) != metrics.executable_or_answerable.n ({expected_exec})"
        )

    has_null_em_f1 = any(
        p.get("em") is None or p.get("f1") is None for p in per_sample_list
    )
    total = metrics.get("total", {})
    em_val = total.get("EM")
    f1_val = total.get("F1")

    if has_null_em_f1:
        if em_val is not None:
            raise ValueError(
                "per-sample em/f1 has None but metrics.total.EM is numeric; must be null"
            )
        if f1_val is not None:
            raise ValueError(
                "per-sample em/f1 has None but metrics.total.F1 is numeric; must be null"
            )
        # failures.csv must have metric_missing rows
        if failures_path.exists():
            with open(failures_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, [])
                rows = list(reader)
            metric_missing_rows = [r for r in rows if len(r) > 5 and r[5] == "metric_missing"]
            if not metric_missing_rows and has_null_em_f1:
                raise ValueError(
                    "per-sample em/f1 is None but failures.csv has no metric_missing rows"
                )
