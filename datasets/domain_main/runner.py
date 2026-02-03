"""Runner helpers for the generic `domain_main` dataset."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Tuple

from core.io import load_jsonl
from .schema import validate_sample_dict


def run_smoke(
    data_file: Path,
    limit: int,
    seed: int,
    log_fn: Callable[[str], None],
) -> Tuple[List[Dict], Dict]:
    """Minimal smoke runner for domain_main.

    It loads up to `limit` samples, validates schema per-sample, and
    returns per-sample result dicts compatible with the existing
    `per_sample_results.jsonl` structure used elsewhere in the framework.
    """
    if limit <= 0:
        raise ValueError(f"limit must be > 0, got {limit}")

    if data_file.exists():
        raw = load_jsonl(data_file)
        log_fn(f"Loaded {len(raw)} samples from {data_file}")
    else:
        log_fn(f"Data file not found: {data_file}; creating dummy samples for smoke")
        raw = [
            {"qid": f"dummy_{i}", "question": f"Dummy question {i}?", "answers": []}
            for i in range(limit)
        ]

    selected = raw[:limit]

    per_sample: List[Dict] = []
    n_ok = 0
    n_bad = 0

    for obj in selected:
        ok, msg = validate_sample_dict(obj)
        status = "ok" if ok else "fail"
        error_type = None if ok else "schema_invalid"
        if ok:
            n_ok += 1
        else:
            n_bad += 1

        per_sample.append(
            {
                "qid": str(obj.get("qid", "")),
                "question": str(obj.get("question", ""))[:120],
                "status": status,
                "is_executable": ok,
                "http_status": None,
                "error_type": error_type,
                "em": None,
                "f1": None,
                "trace_path": None,
            }
        )

    summary = {
        "n_total": len(selected),
        "n_ok": n_ok,
        "n_bad": n_bad,
        "data_file": str(data_file),
        "seed": seed,
    }
    return per_sample, summary

