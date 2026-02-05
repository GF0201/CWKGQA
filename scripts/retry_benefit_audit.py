#!/usr/bin/env python3
"""TASK 17.2: Retry Benefit Audit - 量化 Policy R retry 的净收益。

基于 per_sample_results.jsonl 分析，不重跑模型。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framework.eval import evaluate_prediction  # type: ignore


def _load_jsonl(path: Path) -> list[dict]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Retry Benefit Audit from per_sample_results.jsonl")
    parser.add_argument(
        "--run_dir",
        type=str,
        default="runs/exp_default_config_smoke_real_v1",
        help="Run directory containing artifacts/per_sample_results.jsonl",
    )
    parser.add_argument(
        "--fixed",
        action="store_true",
        help="Use fixed logic: retry_attempted==true, output retry_benefit_audit.fixed.json",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    per_sample_path = run_dir / "artifacts" / "per_sample_results.jsonl"
    if not per_sample_path.exists():
        print(f"Error: not found {per_sample_path}", file=sys.stderr)
        return 1

    metrics_path = run_dir / "metrics.json"
    policy = ""
    if metrics_path.exists():
        try:
            m = json.loads(metrics_path.read_text(encoding="utf-8"))
            policy = (m.get("audit") or {}).get("enforcement_policy", "")
        except Exception:
            pass

    samples = _load_jsonl(per_sample_path)
    n_total = len(samples)

    # Fixed logic: retry_trigger_rate based on retry_attempted==true
    # Policy B should not have retry_triggered
    retry_ids: list[str] = []
    retry_cases: list[dict] = []
    use_fixed = args.fixed

    for s in samples:
        if use_fixed:
            if policy == "force_unknown_if_support_lt_0.5":
                continue  # Policy B: no retry
            if s.get("retry_attempted") is True:
                retry_ids.append(s.get("id", ""))
                retry_cases.append(s)
        else:
            action = s.get("enforcement_action", "")
            has_retry_fields = "raw_answer_retry" in s
            if has_retry_fields or (action in ("retry", "retry_resolved", "retry_then_force_unknown", "force_unknown") and s.get("evidence_violation")):
                retry_ids.append(s.get("id", ""))
                retry_cases.append(s)

    n_retry_triggered = len(retry_cases)
    retry_trigger_rate = n_retry_triggered / n_total if n_total else 0.0

    # Outcomes
    improved = 0
    unchanged = 0
    worsened = 0
    forced_unknown = 0
    f1_before_list: list[float] = []
    f1_after_list: list[float] = []
    em_before_list: list[float] = []
    em_after_list: list[float] = []
    top_examples: list[dict] = []

    for s in retry_cases:
        golds = s.get("gold_answers") or []
        raw_answer = (s.get("raw_answer") or "").strip()
        raw_retry = (s.get("raw_answer_retry") or "").strip()
        final_answer = (s.get("final_answer") or s.get("prediction") or "").strip()

        em_before, f1_before = evaluate_prediction(raw_answer, golds)
        # after_retry = final_answer (stored prediction) and its em/f1
        em_after = 1 if s.get("em") else 0
        f1_after = float(s.get("f1", 0.0))

        f1_before_list.append(f1_before)
        f1_after_list.append(f1_after)
        em_before_list.append(float(em_before))
        em_after_list.append(float(em_after))

        action = s.get("enforcement_action", "")
        if use_fixed:
            if action == "retry_then_force_unknown":
                forced_unknown += 1
            elif action == "retry_resolved":
                if f1_after > f1_before:
                    improved += 1
                elif f1_after < f1_before:
                    worsened += 1
                else:
                    unchanged += 1
        else:
            if final_answer.upper() == "UNKNOWN":
                forced_unknown += 1
            elif f1_after > f1_before:
                improved += 1
            elif f1_after < f1_before:
                worsened += 1
            else:
                unchanged += 1

        ex = {
            "id": s.get("id", ""),
            "question": s.get("question", ""),
            "gold": (golds[0] if golds else ""),
            "raw_answer_before_retry": raw_answer,
            "evidence_before_retry": s.get("evidence_line_ids", []),
            "support_before_retry": s.get("evidence_support"),
            "raw_answer_retry": raw_retry,
            "evidence_retry": s.get("evidence_line_ids_retry", []),
            "support_retry": s.get("evidence_support_retry"),
            "final_answer": final_answer,
            "em_before": 1 if em_before else 0,
            "em_after": em_after,
            "f1_before": f1_before,
            "f1_after": f1_after,
        }
        top_examples.append(ex)

    # Sort by improvement (f1_after - f1_before) desc, then by f1_after desc
    top_examples.sort(key=lambda x: (x["f1_after"] - x["f1_before"], x["f1_after"]), reverse=True)
    top_examples = top_examples[:10]

    mean_f1_before = sum(f1_before_list) / len(f1_before_list) if f1_before_list else 0.0
    mean_f1_after = sum(f1_after_list) / len(f1_after_list) if f1_after_list else 0.0
    mean_em_before = sum(em_before_list) / len(em_before_list) if em_before_list else 0.0
    mean_em_after = sum(em_after_list) / len(em_after_list) if em_after_list else 0.0

    overall_em = sum(1 for x in samples if x.get("em")) / n_total if n_total else 0.0
    overall_f1 = sum(float(x.get("f1", 0)) for x in samples) / n_total if n_total else 0.0

    retry_resolved = sum(1 for s in retry_cases if s.get("enforcement_action") == "retry_resolved")
    retry_then_force = sum(1 for s in retry_cases if s.get("enforcement_action") == "retry_then_force_unknown")

    report = {
        "n_total": n_total,
        "n_retry_triggered": n_retry_triggered,
        "retry_trigger_rate": retry_trigger_rate,
        "retry_attempted_count": n_retry_triggered if use_fixed else None,
        "resolved_count": retry_resolved if use_fixed else None,
        "retry_then_force_unknown_count": retry_then_force if use_fixed else None,
        "outcomes": {
            "improved_after_retry_count": improved,
            "unchanged_after_retry_count": unchanged,
            "worsened_after_retry_count": worsened,
            "forced_unknown_after_retry_count": forced_unknown,
        },
        "metrics_deltas_on_retry_cases": {
            "mean_f1_before_retry": mean_f1_before,
            "mean_f1_after_retry": mean_f1_after,
            "mean_em_before_retry": mean_em_before,
            "mean_em_after_retry": mean_em_after,
        },
        "top_examples": top_examples,
        "list_retry_ids": retry_ids,
    }

    out_name = "retry_benefit_audit.fixed.json" if use_fixed else "retry_benefit_audit.json"
    out_path = run_dir / "artifacts" / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")

    # Console summary
    print("\n=== Retry Benefit Audit Summary ===")
    print(f"Overall EM/F1: {overall_em:.4f} / {overall_f1:.4f}")
    print(f"retry_trigger_rate: {retry_trigger_rate:.4f} ({n_retry_triggered}/{n_total})")
    print(f"On retry cases: mean_f1 before={mean_f1_before:.4f} after={mean_f1_after:.4f} delta={mean_f1_after - mean_f1_before:+.4f}")
    print(f"On retry cases: mean_em before={mean_em_before:.4f} after={mean_em_after:.4f} delta={mean_em_after - mean_em_before:+.4f}")
    print(f"improved={improved} unchanged={unchanged} worsened={worsened} forced_unknown={forced_unknown}")
    if use_fixed:
        print(f"retry_attempted_count={n_retry_triggered} resolved_count={retry_resolved} retry_then_force_unknown_count={retry_then_force}")
    print(f"Top example ids: {[e['id'] for e in top_examples]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
