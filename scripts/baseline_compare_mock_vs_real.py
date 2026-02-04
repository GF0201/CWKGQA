#!/usr/bin/env python3
"""Compare mock vs real baseline runs based on existing artifacts only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pack_run(run_dir: Path) -> dict:
    artifacts = run_dir / "artifacts"
    metrics = _load_json(run_dir / "metrics.json")
    len_hit = _load_json(artifacts / "baseline_len_hit_summary.json")
    taxonomy = _load_json(artifacts / "baseline_error_taxonomy_summary.json")
    failure = _load_json(artifacts / "generator_failure_summary.json")

    total = metrics.get("total", {})
    return {
        "EM": total.get("EM", 0.0),
        "F1": total.get("F1", 0.0),
        "taxonomy_ratios": taxonomy.get("ratios", {}),
        "pred_len_char": len_hit.get("pred_len_char", {}),
        "gold_len_char": len_hit.get("gold_len_char", {}),
        "gold_token_hit_rate": len_hit.get("gold_token_hit_rate", {}),
        "f1_summary": len_hit.get("f1", {}),
        "generator_failure": {
            "prediction_empty_or_whitespace": failure.get("prediction_empty_or_whitespace", {}),
            "prediction_nonempty_but_very_short_le1_token": failure.get(
                "prediction_nonempty_but_very_short_le1_token", {}
            ),
            "error_fields_present": failure.get("error_fields_present", {}),
            "run_log_mention_counts": failure.get("run_log_mention_counts", {}),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock_run_dir", type=str, required=True)
    parser.add_argument("--real_run_dir", type=str, required=True)
    args = parser.parse_args()

    mock_dir = Path(args.mock_run_dir)
    real_dir = Path(args.real_run_dir)

    out = {
        "mock_run_dir": str(mock_dir),
        "real_run_dir": str(real_dir),
        "mock": _pack_run(mock_dir),
        "real": _pack_run(real_dir),
    }

    out_path = real_dir / "artifacts" / "baseline_compare_mock_vs_real.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

