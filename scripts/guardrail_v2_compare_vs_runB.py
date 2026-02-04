#!/usr/bin/env python3
"""Compare evidence-bounded guardrail v2 run vs baseline Run B (answer+evidence).

输出：guardrail_v2_compare_vs_runB.json，包含：
- EM/F1
- taxonomy ratios
- quality gates
- pred_len_char (median/p90 等)
- evidence_line_parse_report / evidence_support_summary
- evidence_violation_rate + enforcement_action breakdown（仅 guardrail v2）
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pack_run(run_dir: Path, with_guardrail: bool) -> Dict[str, Any]:
    artifacts = run_dir / "artifacts"
    metrics = _load_json(run_dir / "metrics.json")
    taxonomy = _load_json(artifacts / "baseline_error_taxonomy_summary.json")
    len_hit = _load_json(artifacts / "baseline_len_hit_summary.json")
    gates = _load_json(artifacts / "answer_quality_gates.json")
    parse_report = _load_json(artifacts / "evidence_line_parse_report.json")
    support_summary = _load_json(artifacts / "evidence_support_summary.json")

    total = metrics.get("total", {})
    out: Dict[str, Any] = {
        "EM": total.get("EM", 0.0),
        "F1": total.get("F1", 0.0),
        "taxonomy_ratios": taxonomy.get("ratios", {}),
        "pred_len_char": len_hit.get("pred_len_char", {}),
        "answer_quality_gates": gates,
        "evidence_line_parse_report": parse_report,
        "evidence_support_summary": support_summary,
    }

    if with_guardrail:
        violation_path = artifacts / "evidence_violation_report.json"
        if violation_path.exists():
            out["evidence_violation_report"] = _load_json(violation_path)
        else:
            out["evidence_violation_report"] = {}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run_baseline_b",
        type=str,
        required=True,
        help="Run dir for baseline Run B (answer+evidence).",
    )
    parser.add_argument(
        "--run_guardrail_v2",
        type=str,
        required=True,
        help="Run dir for guardrail evidence-bounded v2.",
    )
    parser.add_argument(
        "--output_run_dir",
        type=str,
        required=True,
        help="Where to write guardrail_v2_compare_vs_runB.json (under artifacts/).",
    )
    args = parser.parse_args()

    run_b = Path(args.run_baseline_b)
    run_g = Path(args.run_guardrail_v2)

    summary = {
        "baseline_answer_plus_evidence": _pack_run(run_b, with_guardrail=False),
        "guardrail_evidence_bounded_v2": _pack_run(run_g, with_guardrail=True),
    }

    out_run = Path(args.output_run_dir)
    artifacts_dir = out_run / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifacts_dir / "guardrail_v2_compare_vs_runB.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

