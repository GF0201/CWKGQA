#!/usr/bin/env python3
"""Compare Policy B vs Policy R enforcement policy runs (TASK 15).

输出：artifacts/enforcement_policy_compare.json
字段：EM/F1, taxonomy ratios, quality gates, pred_len_char, evidence_violation_rate,
enforcement_action breakdown, violation_ids 逐条对比（Policy B vs Policy R 的 final_answer）
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def _pack_run(run_dir: Path) -> Dict[str, Any]:
    artifacts = run_dir / "artifacts"
    metrics = _load_json(run_dir / "metrics.json")
    taxonomy = _load_json(artifacts / "baseline_error_taxonomy_summary.json")
    len_hit = _load_json(artifacts / "baseline_len_hit_summary.json")
    gates = _load_json(artifacts / "answer_quality_gates.json")
    violation_report = _load_json(artifacts / "evidence_violation_report.json")
    support_summary = _load_json(artifacts / "evidence_support_summary.json")

    total = metrics.get("total", {})
    audit = metrics.get("audit", {})
    return {
        "EM": total.get("EM", 0.0),
        "F1": total.get("F1", 0.0),
        "n": total.get("n", 0),
        "taxonomy_ratios": taxonomy.get("ratios", {}),
        "taxonomy_counts": taxonomy.get("counts", {}),
        "pred_len_char": len_hit.get("pred_len_char", {}),
        "answer_quality_gates": gates,
        "evidence_violation_rate": violation_report.get("evidence_violation_rate", 0.0),
        "violation_ids": violation_report.get("violation_ids", []),
        "enforcement_action_counts": violation_report.get("enforcement_action_counts", {}),
        "evidence_support_summary": support_summary,
        "enforcement_policy": audit.get("enforcement_policy", ""),
    }


def _violation_ids_comparison(
    run_b_dir: Path,
    run_r_dir: Path,
) -> Dict[str, Any]:
    """对比 violation_ids：Policy B vs Policy R 的 final_answer 是否从 UNKNOWN 变为非 UNKNOWN/正确。"""
    arts_b = run_b_dir / "artifacts" / "per_sample_results.jsonl"
    arts_r = run_r_dir / "artifacts" / "per_sample_results.jsonl"
    samples_b = {s["id"]: s for s in _load_jsonl(arts_b)}
    samples_r = {s["id"]: s for s in _load_jsonl(arts_r)}

    violation_report_b = _load_json(run_b_dir / "artifacts" / "evidence_violation_report.json")
    violation_ids = violation_report_b.get("violation_ids", [])

    comparison = []
    for vid in violation_ids:
        sb = samples_b.get(vid, {})
        sr = samples_r.get(vid, {})
        pred_b = (sb.get("final_answer") or sb.get("prediction") or "").strip()
        pred_r = (sr.get("final_answer") or sr.get("prediction") or "").strip()
        em_r = sr.get("em", False)
        f1_r = sr.get("f1", 0.0)
        b_unknown = pred_b.upper() == "UNKNOWN"
        r_unknown = pred_r.upper() == "UNKNOWN"
        improved = b_unknown and not r_unknown
        correct_after_r = improved and (em_r or f1_r > 0)
        comparison.append({
            "id": vid,
            "policy_B_final_answer": pred_b,
            "policy_R_final_answer": pred_r,
            "policy_B_unknown": b_unknown,
            "policy_R_unknown": r_unknown,
            "improved_to_non_unknown": improved,
            "correct_after_retry": correct_after_r,
            "em_after_R": em_r,
            "f1_after_R": f1_r,
        })

    n_improved = sum(1 for c in comparison if c["improved_to_non_unknown"])
    n_correct_after = sum(1 for c in comparison if c["correct_after_retry"])
    return {
        "violation_ids": violation_ids,
        "per_id_comparison": comparison,
        "n_improved_to_non_unknown": n_improved,
        "n_correct_after_retry": n_correct_after,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Policy B vs Policy R enforcement policy runs")
    parser.add_argument(
        "--run_policy_b",
        type=str,
        required=True,
        help="Run dir for Policy B (force_unknown_if_support_lt_0.5)",
    )
    parser.add_argument(
        "--run_policy_r",
        type=str,
        required=True,
        help="Run dir for Policy R (retry_once_if_support_lt_0.5_else_force_unknown)",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Output dir for enforcement_policy_compare.json; default: run_policy_r",
    )
    args = parser.parse_args()

    run_b = Path(args.run_policy_b)
    run_r = Path(args.run_policy_r)
    if not run_b.exists():
        print(f"Error: run_policy_b not found: {run_b}", file=__import__("sys").stderr)
        return 1
    if not run_r.exists():
        print(f"Error: run_policy_r not found: {run_r}", file=__import__("sys").stderr)
        return 1

    pack_b = _pack_run(run_b)
    pack_r = _pack_run(run_r)
    violation_comparison = _violation_ids_comparison(run_b, run_r)

    summary = {
        "policy_B": pack_b,
        "policy_R": pack_r,
        "violation_ids_comparison": violation_comparison,
        "delta": {
            "EM": pack_r["EM"] - pack_b["EM"],
            "F1": pack_r["F1"] - pack_b["F1"],
            "unknown_rate_B": pack_b.get("answer_quality_gates", {}).get("unknown_rate", 0.0),
            "unknown_rate_R": pack_r.get("answer_quality_gates", {}).get("unknown_rate", 0.0),
        },
    }

    out_dir = Path(args.output_dir) if args.output_dir else run_r
    artifacts_dir = out_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifacts_dir / "enforcement_policy_compare.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
