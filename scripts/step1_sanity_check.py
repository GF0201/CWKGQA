#!/usr/bin/env python3
"""Step 1: Sanity check - 空输出与异常原因归因."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framework.eval import mixed_segmentation, normalize_answer  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", type=str, default="runs/exp_baseline_20260203_230544")
    args = parser.parse_args()

    run_dir = ROOT / args.run_dir
    artifacts_dir = run_dir / "artifacts"
    per_sample_path = artifacts_dir / "per_sample_results.jsonl"
    run_log_path = run_dir / "run.log"

    if not per_sample_path.exists():
        print(f"Missing: {per_sample_path}", file=sys.stderr)
        return 1

    samples = []
    with open(per_sample_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    n = len(samples)
    empty_count = 0
    very_short_count = 0  # <=1 token
    empty_ids = []
    error_fields: Counter[str] = Counter()
    top_errors: list[str] = []

    for s in samples:
        pred = (s.get("prediction") or "").strip()
        pred_norm = normalize_answer(pred)
        tokens = mixed_segmentation(pred_norm)
        if not pred:
            empty_count += 1
            empty_ids.append(s.get("id", ""))
        elif len(tokens) <= 1:
            very_short_count += 1
        for k in ("error", "exception", "http_status", "timeout", "retries"):
            if k in s and s[k] is not None and str(s[k]).strip():
                error_fields[k] += 1
                msg = str(s.get(k, ""))[:100]
                if msg and msg not in top_errors:
                    top_errors.append(msg)

    # Run.log analysis
    log_text = ""
    if run_log_path.exists():
        log_text = run_log_path.read_text(encoding="utf-8")
    http_err = len(re.findall(r"HTTP|status.*5\d{2}|Connection refused|Failed to establish", log_text, re.I))
    timeout_cnt = len(re.findall(r"timeout|timed out", log_text, re.I))
    parse_cnt = len(re.findall(r"JSON|decode|missing.*choices|parse", log_text, re.I))

    failure_summary = {
        "n_total": n,
        "prediction_empty_or_whitespace": {"count": empty_count, "ratio": round(empty_count / n, 4) if n else 0},
        "prediction_nonempty_but_very_short_le1_token": {"count": very_short_count, "ratio": round(very_short_count / n, 4) if n else 0},
        "error_fields_present": dict(error_fields),
        "run_log_mention_counts": {
            "http_error_like": http_err,
            "timeout_like": timeout_cnt,
            "parse_fail_like": parse_cnt,
        },
        "top_error_messages": top_errors[:10],
    }

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "generator_failure_summary.json").write_text(
        json.dumps(failure_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (artifacts_dir / "empty_prediction_ids.json").write_text(
        json.dumps(empty_ids, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote generator_failure_summary.json, empty_prediction_ids.json (n_empty={empty_count})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
