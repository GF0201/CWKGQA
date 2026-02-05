#!/usr/bin/env python3
"""Compare multiple baseline runs with/without intent module.

Usage:
    python scripts/intent_ablation_compare.py --runs exp_no_intent_real_v1 exp_intent_rule_v1_real_v1 ...

Output:
    artifacts/intent_ablation_compare.json
        {
          "<run_id>": {
            "metrics": {EM, F1, n},
            "unknown_rate": float,
            "intent": {
               "module_enabled": bool,
               "multi_intent_rate": float | null,
               "ambiguous_rate": float | null,
               "coverage_rate": float | null
            },
            "intent_label_top1": {...}
          },
          ...
        }
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is on sys.path so that `framework` and other top-level
# modules can be imported correctly when running this script directly.
import sys

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.utils import ROOT, RUNS_DIR, ensure_dir, load_jsonl  # type: ignore


def _load_metrics(run_dir: Path) -> Dict[str, Any]:
    m_path = run_dir / "metrics.json"
    if not m_path.exists():
        raise FileNotFoundError(f"metrics.json not found in {run_dir}")
    return json.loads(m_path.read_text(encoding="utf-8"))


def _load_per_sample(run_dir: Path) -> List[Dict[str, Any]]:
    ps_path = run_dir / "artifacts" / "per_sample_results.jsonl"
    if not ps_path.exists():
        return []
    return load_jsonl(ps_path)


def _summarize_run(run_id: str) -> Dict[str, Any]:
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Run dir not found: {run_dir}")

    metrics = _load_metrics(run_dir)
    per_sample = _load_per_sample(run_dir)

    total = metrics.get("total", {}) or {}
    n = int(total.get("n", len(per_sample)))
    em = float(total.get("EM", 0.0) or 0.0)
    f1 = float(total.get("F1", 0.0) or 0.0)

    unknown_rate = None
    format_mismatch_rate = None
    ungrounded_or_wrong_rate = None
    if per_sample:
        n_unknown = 0
        n_format_mismatch = 0
        n_uw = 0
        for s in per_sample:
            final_ans = str(s.get("final_answer") or s.get("prediction") or "")
            if final_ans == "UNKNOWN":
                n_unknown += 1
            # 可选字段：如果样本中显式标注了 format_mismatch / ungrounded_or_wrong，则汇总其频率
            if s.get("format_mismatch"):
                n_format_mismatch += 1
            if s.get("ungrounded_or_wrong"):
                n_uw += 1
        total_ps = len(per_sample)
        unknown_rate = n_unknown / total_ps if total_ps else None
        format_mismatch_rate = n_format_mismatch / total_ps if total_ps else None
        ungrounded_or_wrong_rate = n_uw / total_ps if total_ps else None

    audit = metrics.get("audit", {}) or {}
    intent_enabled = bool(audit.get("intent_module_enabled"))
    intent_multi = audit.get("intent_multi_intent_rate")
    intent_amb = audit.get("intent_ambiguous_rate")
    intent_cov = audit.get("intent_coverage_rate")

    # top1 intent label 分布（若存在 intent_pred）
    intent_label_top1: Dict[str, Any] = {}
    if per_sample:
        label_counter = Counter()
        for s in per_sample:
            ip = s.get("intent_pred") or {}
            intents = ip.get("intents") or []
            if intents:
                label_counter[str(intents[0].get("label"))] += 1
        total_top1 = sum(label_counter.values())
        for label, cnt in label_counter.items():
            intent_label_top1[label] = {
                "count": cnt,
                "ratio": cnt / total_top1 if total_top1 else 0.0,
            }

    return {
        "metrics": {"n": n, "EM": em, "F1": f1},
        "unknown_rate": unknown_rate,
        "format_mismatch_rate": format_mismatch_rate,
        "ungrounded_or_wrong_rate": ungrounded_or_wrong_rate,
        "intent": {
            "module_enabled": intent_enabled,
            "multi_intent_rate": intent_multi,
            "ambiguous_rate": intent_amb,
            "coverage_rate": intent_cov,
        },
        "intent_label_top1": intent_label_top1,
        "ablation": audit.get("ablation"),
        "contract_variant": audit.get("contract_variant"),
        "enforcement_policy": audit.get("enforcement_policy"),
        "retriever_type": audit.get("retriever_type"),
        "retriever_topk": audit.get("retriever_topk"),
        "intent_mode": audit.get("intent_mode"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare multiple runs for intent ablation.")
    parser.add_argument(
        "--runs",
        nargs="+",
        required=True,
        help=(
            "Run ids under runs/ to compare (e.g., "
            "exp_no_intent_real_v1 exp_intent_rule_v1_real_v1 ...)."
        ),
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="artifacts",
        help=(
            "Output directory (relative to repo root) for compare artifacts. "
            "Default: artifacts/"
        ),
    )
    args = parser.parse_args()

    out: Dict[str, Any] = {}
    for run_id in args.runs:
        summary = _summarize_run(run_id)
        out[run_id] = summary

    artifacts_dir = ensure_dir(ROOT / args.output_dir)
    # 1) JSON 总表
    json_path = artifacts_dir / "intent_ablation_compare.json"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2) 主表 CSV：逐 run 摘要
    import csv  # type: ignore

    main_csv_path = artifacts_dir / "intent_ablation_main_table.csv"
    fieldnames = [
        "run_id",
        "intent_mode",
        "EM",
        "F1",
        "unknown_rate",
        "ungrounded_or_wrong_rate",
        "format_mismatch_rate",
        "multi_intent_rate",
        "ambiguous_rate",
        "intent_coverage_rate",
        "contract_variant",
        "enforcement_policy",
        "retriever_type",
        "retriever_topk",
    ]
    with open(main_csv_path, "w", newline="", encoding="utf-8") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=fieldnames)
        writer.writeheader()
        for run_id, summary in out.items():
            metrics = summary.get("metrics", {}) or {}
            intent = summary.get("intent", {}) or {}
            row = {
                "run_id": run_id,
                "intent_mode": summary.get("intent_mode"),
                "EM": metrics.get("EM"),
                "F1": metrics.get("F1"),
                "unknown_rate": summary.get("unknown_rate"),
                "ungrounded_or_wrong_rate": summary.get("ungrounded_or_wrong_rate"),
                "format_mismatch_rate": summary.get("format_mismatch_rate"),
                "multi_intent_rate": intent.get("multi_intent_rate"),
                "ambiguous_rate": intent.get("ambiguous_rate"),
                "intent_coverage_rate": intent.get("coverage_rate"),
                "contract_variant": summary.get("contract_variant"),
                "enforcement_policy": summary.get("enforcement_policy"),
                "retriever_type": summary.get("retriever_type"),
                "retriever_topk": summary.get("retriever_topk"),
            }
            writer.writerow(row)

    # 3) 触发统计 CSV：按 top1 intent label 的聚合视角
    trigger_csv_path = artifacts_dir / "intent_trigger_stats.csv"
    fieldnames_trigger = ["run_id", "intent_label", "count", "ratio"]
    with open(trigger_csv_path, "w", newline="", encoding="utf-8") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=fieldnames_trigger)
        writer.writeheader()
        for run_id, summary in out.items():
            label_stats = summary.get("intent_label_top1") or {}
            for label, info in label_stats.items():
                writer.writerow(
                    {
                        "run_id": run_id,
                        "intent_label": label,
                        "count": info.get("count"),
                        "ratio": info.get("ratio"),
                    }
                )

    print(f"Wrote {json_path}")
    print(f"Wrote {main_csv_path}")
    print(f"Wrote {trigger_csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

