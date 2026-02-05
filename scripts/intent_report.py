#!/usr/bin/env python3
"""Run IntentEngine over QA test set and produce intent_report.json.

Input:
    datasets/domain_main_qa/test.jsonl  (默认，可通过 --input 覆盖)

Output:
    runs/<run_id>/artifacts/intent_report.json

统计字段包括：
    - per_label counts & ratios
    - multi_intent_rate, ambiguous_rate
    - top trigger rules (按出现次数统计)
    - conflict-like cases（同时高分命中冲突标签对的样本 id）
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from framework.utils import ROOT, RUNS_DIR, ensure_dir, load_jsonl  # type: ignore
from core import DualLogger, write_repro_manifest  # type: ignore
from src.intent.intent_engine import IntentEngine  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser(description="IntentEngine report over QA dataset")
    parser.add_argument(
        "--input",
        type=str,
        default="datasets/domain_main_qa/test.jsonl",
        help="QA JSONL file with fields: id, question",
    )
    parser.add_argument(
        "--run_id",
        type=str,
        default=None,
        help="Run id under runs/; default: intent_report_<timestamp>",
    )
    args = parser.parse_args()

    run_id = args.run_id or f"intent_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = RUNS_DIR / run_id
    artifacts_dir = ensure_dir(run_dir / "artifacts")

    logger = DualLogger(run_dir, "run.log")
    start_time = datetime.now().isoformat()

    engine = IntentEngine()
    audit_info = engine.get_audit_info()

    input_path = ROOT / args.input if not Path(args.input).is_absolute() else Path(args.input)
    rows = load_jsonl(input_path)
    n = len(rows)
    logger.log(f"[intent_report] run_id={run_id}, input={input_path}, n={n}")

    label_counter = Counter()
    multi_count = 0
    amb_count = 0
    rule_counter = Counter()
    conflict_cases: List[str] = []

    # 为 conflict 统计保留 top2 label 信息
    from src.intent.intent_engine import INTENT_RULES_PATH  # type: ignore
    import yaml

    rules_cfg = yaml.safe_load(INTENT_RULES_PATH.read_text(encoding="utf-8")) or {}
    raw_pairs = rules_cfg.get("conflict_matrix") or []
    conflict_pairs = {(str(a), str(b)) for a, b in raw_pairs if len([a, b]) == 2}
    conflict_pairs |= {(b, a) for (a, b) in conflict_pairs}

    for row in rows:
        qid = row.get("id") or row.get("qid") or ""
        q = row.get("question") or ""
        out = engine.predict(str(q))
        intents = out.get("intents") or []

        if intents:
            # 统计每条样本 top1 label
            top1 = intents[0]["label"]
            label_counter[top1] += 1

            # 规则触发统计
            for it in intents:
                for ev in it.get("evidence_rules_triggered") or []:
                    rule_counter[ev.get("rule_id", "")] += 1

            # 冲突案例统计（top2 标签互为 conflict pair）
            if len(intents) >= 2:
                a = intents[0]["label"]
                b = intents[1]["label"]
                if (a, b) in conflict_pairs:
                    conflict_cases.append(str(qid))

        if out.get("is_multi_intent"):
            multi_count += 1
        if out.get("is_ambiguous"):
            amb_count += 1

    report: Dict[str, Any] = {
        "n_samples": n,
        "per_label": {},
        "multi_intent_rate": (multi_count / n) if n else 0.0,
        "ambiguous_rate": (amb_count / n) if n else 0.0,
        "top_trigger_rules": [],
        "conflict_case_ids": conflict_cases,
        "intent_audit": audit_info,
    }

    for label, cnt in label_counter.items():
        report["per_label"][label] = {
            "count": cnt,
            "ratio": cnt / n if n else 0.0,
        }

    for rid, cnt in rule_counter.most_common(20):
        if not rid:
            continue
        report["top_trigger_rules"].append(
            {
                "rule_id": rid,
                "count": cnt,
                "ratio": cnt / n if n else 0.0,
            }
        )

    out_path = artifacts_dir / "intent_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.log(f"[intent_report] wrote {out_path}")

    # 轻量 repro_manifest（简化版，但仍记录 config 指纹）
    end_time = datetime.now().isoformat()
    write_repro_manifest(
        run_dir,
        run_id=run_id,
        start_time=start_time,
        end_time=end_time,
        command_argv=sys.argv,
        seed=0,
        inputs=[input_path, INTENT_RULES_PATH, ROOT / "configs" / "intent_taxonomy.yaml"],
        config_dict={
            "intent_taxonomy_path": str(INTENT_RULES_PATH),
            "intent_rules_path": str(ROOT / "configs" / "intent_rules.yaml"),
            "intent_audit": audit_info,
        },
        args={"input": str(input_path)},
        warnings=[],
        old_dir=None,
        data_file=input_path,
        extra_fields={"phase": "intent_report"},
    )

    logger.log("[intent_report] done")
    logger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

