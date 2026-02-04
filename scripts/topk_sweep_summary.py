#!/usr/bin/env python3
"""Generate top-k sweep summary for multiple runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pack_run(run_dir: Path) -> dict:
    artifacts = run_dir / "artifacts"
    metrics = _load_json(run_dir / "metrics.json")
    taxonomy = _load_json(artifacts / "baseline_error_taxonomy_summary.json")
    len_hit = _load_json(artifacts / "baseline_len_hit_summary.json")
    gates = _load_json(artifacts / "answer_quality_gates.json")

    total = metrics.get("total", {})
    return {
        "EM": total.get("EM", 0.0),
        "F1": total.get("F1", 0.0),
        "taxonomy_ratios": taxonomy.get("ratios", {}),
        "pred_len_char": len_hit.get("pred_len_char", {}),
        "gold_len_char": len_hit.get("gold_len_char", {}),
        "answer_quality_gates": gates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dirs", type=str, nargs="+", required=True)
    parser.add_argument(
        "--output_run_dir",
        type=str,
        default="runs/exp_baseline_real_v1",
        help="Where to write topk_sweep_summary.json (under artifacts/).",
    )
    args = parser.parse_args()

    summary = {}
    for rd in args.run_dirs:
        run_dir = Path(rd)
        metrics = _load_json(run_dir / "metrics.json")
        audit = metrics.get("audit", {})
        k = audit.get("retriever_topk")
        summary[str(k)] = _pack_run(run_dir)

    out_run = Path(args.output_run_dir)
    out_path = out_run / "artifacts" / "topk_sweep_summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

