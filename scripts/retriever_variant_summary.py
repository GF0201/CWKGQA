#!/usr/bin/env python3
"""Generate retriever variant summary (simple vs bm25)."""
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
    audit = metrics.get("audit", {})
    return {
        "EM": total.get("EM", 0.0),
        "F1": total.get("F1", 0.0),
        "taxonomy_ratios": taxonomy.get("ratios", {}),
        "pred_len_char": len_hit.get("pred_len_char", {}),
        "gold_len_char": len_hit.get("gold_len_char", {}),
        "answer_quality_gates": gates,
        "retriever_type": audit.get("retriever_type"),
        "retriever_topk": audit.get("retriever_topk"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simple_run_dir", type=str, required=True)
    parser.add_argument("--bm25_run_dir", type=str, required=True)
    parser.add_argument(
        "--output_run_dir",
        type=str,
        default="runs/exp_baseline_real_v1",
        help="Where to write retriever_variant_summary.json (under artifacts/).",
    )
    args = parser.parse_args()

    simple_dir = Path(args.simple_run_dir)
    bm25_dir = Path(args.bm25_run_dir)

    summary = {
        "simple": _pack_run(simple_dir),
        "bm25": _pack_run(bm25_dir),
    }

    out_run = Path(args.output_run_dir)
    out_path = out_run / "artifacts" / "retriever_variant_summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

