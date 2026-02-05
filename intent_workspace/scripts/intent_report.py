#!/usr/bin/env python3
"""intent_workspace-level intent report.

- 读取指定 input（默认与 intent_experiment_defaults.yaml 一致）
- 使用全局 IntentEngine（src/intent/intent_engine.py）跑一遍 prediction
- 写出 intent_report.json 到 intent_workspace/runs/<run_id>/
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is on sys.path so that `core`, `framework`, etc. can be
# imported correctly when running this script directly.
import sys

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core import DualLogger  # type: ignore
from framework.utils import load_jsonl  # type: ignore
from src.intent.intent_engine import IntentEngine  # type: ignore

from intent_workspace.src.utils import ROOT  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser(description="intent_workspace intent report")
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="QA JSONL file; default from intent_experiment_defaults.yaml.",
    )
    parser.add_argument(
        "--run_id",
        type=str,
        default=None,
        help="Run id under intent_workspace/runs/; default: intent_report_<timestamp>",
    )
    args = parser.parse_args()

    # 默认 input 来自 intent_experiment_defaults.yaml
    defaults_path = ROOT / "intent_workspace" / "configs" / "intent_experiment_defaults.yaml"
    import yaml

    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8")) or {}
    input_rel = args.input or defaults.get(
        "default_input_path", "datasets/domain_main_qa/test.jsonl"
    )
    input_path = ROOT / input_rel if not Path(input_rel).is_absolute() else Path(input_rel)

    runs_base = ROOT / "intent_workspace" / "runs"
    runs_base.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or f"intent_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = runs_base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = DualLogger(run_dir, "run.log")
    start_time = datetime.now().isoformat()
    logger.log(f"[intent_report_ws] run_id={run_id}")
    logger.log(f"[intent_report_ws] input={input_path}")

    engine = IntentEngine()
    audit_info = engine.get_audit_info()

    rows = load_jsonl(input_path)
    n = len(rows)
    logger.log(f"[intent_report_ws] n={n}")

    label_counter = Counter()
    multi = 0
    amb = 0
    rule_counter = Counter()

    for row in rows:
        q = row.get("question") or ""
        out = engine.predict(str(q))
        intents = out.get("intents") or []
        if intents:
            top1 = intents[0]["label"]
            label_counter[top1] += 1
            for it in intents:
                for ev in it.get("evidence_rules_triggered") or []:
                    rule_counter[ev.get("rule_id", "")] += 1
        if out.get("is_multi_intent"):
            multi += 1
        if out.get("is_ambiguous"):
            amb += 1

    report: Dict[str, Any] = {
        "n_samples": n,
        "per_label": {},
        "multi_intent_rate": multi / n if n else 0.0,
        "ambiguous_rate": amb / n if n else 0.0,
        "top_trigger_rules": [],
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
            {"rule_id": rid, "count": cnt, "ratio": cnt / n if n else 0.0}
        )

    out_path = run_dir / "intent_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.log(f"[intent_report_ws] wrote {out_path}")

    logger.log("[intent_report_ws] done")
    logger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

