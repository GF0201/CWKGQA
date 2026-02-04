#!/usr/bin/env python3
"""Recompute evidence support/violation with unified semantics for an existing run.

Semantics:
- Based on raw_answer (parsed from two-line contract), NOT final enforced answer.
- Writes evidence_violation_report.fixed.json and updates metrics.json.audit with
  support_semantics_version and support_module_sha256.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framework.evidence_support import (  # type: ignore
    SUPPORT_SEMANTICS_VERSION,
    parse_contract,
    compute_support,
    get_module_sha256,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", type=str, required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    artifacts_dir = run_dir / "artifacts"
    per_sample_path = artifacts_dir / "per_sample_results.jsonl"
    if not per_sample_path.exists():
        raise SystemExit(f"Missing {per_sample_path}")

    rows: List[Dict[str, Any]] = []
    with per_sample_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    total_n = len(rows)
    violation_ids: List[str] = []
    action_counts: Counter = Counter()

    for s in rows:
        sid = str(s.get("id", ""))
        raw_pred = (s.get("raw_prediction") or s.get("prediction") or "").strip()
        retrieved = s.get("retrieved_triples") or []
        parsed = parse_contract(raw_pred, retrieved_k=len(retrieved))
        raw_answer = parsed.raw_answer
        evidence_ids = parsed.evidence_line_ids

        support = compute_support(raw_answer, evidence_ids, retrieved)
        coverage = support.get("coverage")
        violation = coverage is None or coverage < 0.5
        if violation:
            violation_ids.append(sid)

        action = s.get("enforcement_action", "none")
        action_counts[action] += 1

    violation_rate = len(violation_ids) / total_n if total_n else 0.0
    report = {
        "n": total_n,
        "support_semantics_version": SUPPORT_SEMANTICS_VERSION,
        "evidence_violation_rate": violation_rate,
        "violation_ids": violation_ids,
        "enforcement_action_counts": dict(action_counts),
    }
    out_path = artifacts_dir / "evidence_violation_report.fixed.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")

    # Update metrics audit with support semantics + module fingerprint
    metrics_path = run_dir / "metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    else:
        metrics = {}
    audit = metrics.setdefault("audit", {})
    audit["support_semantics_version"] = SUPPORT_SEMANTICS_VERSION
    audit["support_module_sha256"] = get_module_sha256()
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated audit in {metrics_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

