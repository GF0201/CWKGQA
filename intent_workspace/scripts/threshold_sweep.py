#!/usr/bin/env python3
"""Threshold sweep for IntentEngine v1 (P1‑2).

目标：
- 在不改动主线默认配置的前提下，对
  - multi_label_threshold
  - ambiguous_margin
  - min_confidence
  做小网格扫描；
- 在固定输入集上统计：
  - ambiguous_rate
  - multi_intent_rate
  - coverage_rate
- 记录每组参数对应的 intent_config_fingerprint，写入：
  intent_workspace/artifacts/threshold_sweep_summary.csv

如后续补充了人工 gold（含 gold_intents 字段），可在本脚本基础上扩展
gold_macro_f1 / gold_accuracy 等一致性指标。
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 确保可以导入顶层模块
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.utils import load_jsonl  # type: ignore
from src.intent.intent_engine import IntentEngine  # type: ignore

from intent_workspace.src.utils import (  # type: ignore
    ROOT,
    load_intent_configs,
    build_effective_config,
    compute_config_fingerprint,
)


def _parse_list(arg: str) -> List[float]:
    return [float(x.strip()) for x in arg.split(",") if x.strip()]


def _prepare_intent_config_fingerprint(
    defaults_path: Path,
    *,
    multi_label_threshold: float,
    ambiguous_margin: float,
    min_confidence: float,
) -> str:
    """使用 intent_workspace 的 fingerprint 逻辑为当前阈值组合计算指纹。"""

    defaults, taxonomy, rules = load_intent_configs(defaults_path)
    effective = build_effective_config(defaults, taxonomy, rules, cli_overrides=None)
    # 覆盖 thresholds 字段，以当前组合为准
    effective["thresholds"] = {
        "multi_label_threshold": multi_label_threshold,
        "ambiguous_margin": ambiguous_margin,
        "min_confidence": min_confidence,
    }
    fp, _ = compute_config_fingerprint(effective)
    return fp


def _run_sweep_once(
    questions: List[Dict[str, Any]],
    *,
    multi_label_threshold: float,
    ambiguous_margin: float,
    min_confidence: float,
) -> Dict[str, Any]:
    """在给定阈值组合下运行 IntentEngine 统计三类指标。"""

    engine = IntentEngine()
    engine.thresholds = {
        "multi_label_threshold": float(multi_label_threshold),
        "ambiguous_margin": float(ambiguous_margin),
        "min_confidence": float(min_confidence),
    }

    n = len(questions)
    n_amb = 0
    n_multi = 0
    n_with_any = 0

    for row in questions:
        q = row.get("question") or ""
        out = engine.predict(str(q))
        intents = out.get("intents") or []
        if intents:
            n_with_any += 1
        if out.get("is_ambiguous"):
            n_amb += 1
        if out.get("is_multi_intent"):
            n_multi += 1

    ambiguous_rate = n_amb / n if n else 0.0
    multi_rate = n_multi / n if n else 0.0
    coverage_rate = n_with_any / n if n else 0.0

    return {
        "ambiguous_rate": ambiguous_rate,
        "multi_intent_rate": multi_rate,
        "coverage_rate": coverage_rate,
        "n": n,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Threshold sweep for rule-based IntentEngine.")
    parser.add_argument(
        "--input",
        type=str,
        default="datasets/domain_main_qa/test.jsonl",
        help="QA JSONL file used for sweep (default: datasets/domain_main_qa/test.jsonl).",
    )
    parser.add_argument(
        "--defaults",
        type=str,
        default="intent_workspace/configs/intent_experiment_defaults.yaml",
        help="Intent experiment defaults YAML (for fingerprint computation).",
    )
    parser.add_argument(
        "--multi_label_thresholds",
        type=str,
        default="0.4,0.6,0.8",
        help="Comma-separated list for multi_label_threshold sweep (default: 0.4,0.6,0.8).",
    )
    parser.add_argument(
        "--ambiguous_margins",
        type=str,
        default="0.1,0.15,0.2",
        help="Comma-separated list for ambiguous_margin sweep (default: 0.1,0.15,0.2).",
    )
    parser.add_argument(
        "--min_confidences",
        type=str,
        default="0.3,0.4,0.5",
        help="Comma-separated list for min_confidence sweep (default: 0.3,0.4,0.5).",
    )
    args = parser.parse_args()

    input_path = (ROOT / args.input) if not Path(args.input).is_absolute() else Path(args.input)
    defaults_path = (
        ROOT / args.defaults if not Path(args.defaults).is_absolute() else Path(args.defaults)
    )

    questions = load_jsonl(input_path)
    if not questions:
        print(f"[threshold_sweep] ERROR: input empty: {input_path}", file=sys.stderr)
        return 1

    ml_list = _parse_list(args.multi_label_thresholds)
    amb_list = _parse_list(args.ambiguous_margins)
    minc_list = _parse_list(args.min_confidences)

    artifacts_dir = ROOT / "intent_workspace" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_csv = artifacts_dir / "threshold_sweep_summary.csv"

    fieldnames = [
        "multi_label_threshold",
        "ambiguous_margin",
        "min_confidence",
        "ambiguous_rate",
        "multi_intent_rate",
        "coverage_rate",
        "n",
        "intent_config_fingerprint",
        "gold_macro_f1",
        "gold_accuracy",
    ]

    rows_out: List[Dict[str, Any]] = []
    for ml in ml_list:
        for amb in amb_list:
            for mc in minc_list:
                stats = _run_sweep_once(
                    questions,
                    multi_label_threshold=ml,
                    ambiguous_margin=amb,
                    min_confidence=mc,
                )
                cfg_fp = _prepare_intent_config_fingerprint(
                    defaults_path,
                    multi_label_threshold=ml,
                    ambiguous_margin=amb,
                    min_confidence=mc,
                )
                row = {
                    "multi_label_threshold": ml,
                    "ambiguous_margin": amb,
                    "min_confidence": mc,
                    "ambiguous_rate": stats["ambiguous_rate"],
                    "multi_intent_rate": stats["multi_intent_rate"],
                    "coverage_rate": stats["coverage_rate"],
                    "n": stats["n"],
                    "intent_config_fingerprint": cfg_fp,
                    "gold_macro_f1": None,
                    "gold_accuracy": None,
                }
                rows_out.append(row)

    with open(out_csv, "w", newline="", encoding="utf-8") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows_out:
            writer.writerow(r)

    print(f"[threshold_sweep] wrote {out_csv} with {len(rows_out)} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

