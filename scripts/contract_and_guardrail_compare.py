#!/usr/bin/env python3
"""Generate contract + guardrail comparison summary for three runs.

输出：
- 在指定 output_run_dir/artifacts 下写入 contract_and_guardrail_compare.json：
  - 每个 run 的 EM/F1
  - taxonomy ratios
  - answer quality gates
  - pred_len_char（median/p90 等）
  - （仅 Run B：附加 evidence_line_parse_report + evidence_support_summary）
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pack_run(run_dir: Path, with_evidence: bool) -> Dict[str, Any]:
    artifacts = run_dir / "artifacts"
    metrics = _load_json(run_dir / "metrics.json")
    taxonomy = _load_json(artifacts / "baseline_error_taxonomy_summary.json")
    len_hit = _load_json(artifacts / "baseline_len_hit_summary.json")
    gates = _load_json(artifacts / "answer_quality_gates.json")

    total = metrics.get("total", {})
    out: Dict[str, Any] = {
        "EM": total.get("EM", 0.0),
        "F1": total.get("F1", 0.0),
        "taxonomy_ratios": taxonomy.get("ratios", {}),
        "pred_len_char": len_hit.get("pred_len_char", {}),
        "answer_quality_gates": gates,
    }

    if with_evidence:
        parse_path = artifacts / "evidence_line_parse_report.json"
        support_path = artifacts / "evidence_support_summary.json"
        out["evidence_line_parse_report"] = (
            _load_json(parse_path) if parse_path.exists() else {}
        )
        out["evidence_support_summary"] = (
            _load_json(support_path) if support_path.exists() else {}
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run_answer_only",
        type=str,
        required=True,
        help="Run dir for answer-only contract (Run A).",
    )
    parser.add_argument(
        "--run_answer_plus_evidence",
        type=str,
        required=True,
        help="Run dir for answer+evidence contract (Run B).",
    )
    parser.add_argument(
        "--run_guardrail",
        type=str,
        required=True,
        help="Run dir for guardrail answerable-only contract (Run C).",
    )
    parser.add_argument(
        "--output_run_dir",
        type=str,
        required=True,
        help="Where to write contract_and_guardrail_compare.json (under artifacts/).",
    )
    args = parser.parse_args()

    run_a = Path(args.run_answer_only)
    run_b = Path(args.run_answer_plus_evidence)
    run_c = Path(args.run_guardrail)

    summary = {
        "answer_only": _pack_run(run_a, with_evidence=False),
        "answer_plus_evidence": _pack_run(run_b, with_evidence=True),
        "guardrail_answerable_only": _pack_run(run_c, with_evidence=False),
    }

    out_run = Path(args.output_run_dir)
    artifacts_dir = out_run / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifacts_dir / "contract_and_guardrail_compare.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

