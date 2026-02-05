#!/usr/bin/env python3
"""Smoke test inside intent_workspace.

- 通过 IntentEngine 对少量样例运行 rule_predict 流程
- 写出一个轻量 run 到 intent_workspace/runs/<run_id>/
- 验证 intent_workspace 下的入口与产物结构是否正常工作
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from core import DualLogger  # type: ignore

from intent_workspace.src.intent_engine import run_rule_predict  # type: ignore
from intent_workspace.src.utils import ROOT, get_git_commit  # type: ignore


def main() -> int:
    defaults_path = ROOT / "intent_workspace" / "configs" / "intent_experiment_defaults.yaml"
    if not defaults_path.exists():
        print(f"Defaults not found: {defaults_path}", file=sys.stderr)
        return 1

    import yaml

    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8")) or {}
    input_rel = defaults.get(
        "default_input_path", "datasets/domain_main_qa/test.jsonl"
    )
    input_path = ROOT / input_rel
    if not input_path.exists():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 1

    output_base = ROOT / "intent_workspace" / "runs"
    output_base.mkdir(parents=True, exist_ok=True)
    run_id = f"intent_smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = output_base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = DualLogger(run_dir, "run.log")
    logger.log(f"[intent_smoke] run_id={run_id}")

    metrics, per_sample, config_snapshot, config_fingerprint = run_rule_predict(
        project_root=ROOT,
        input_path=input_path,
        defaults_path=defaults_path,
        run_dir=run_dir,
        logger=logger,
    )

    from core import save_jsonl  # type: ignore

    per_sample_path = run_dir / "per_sample_intent_results.jsonl"
    save_jsonl(per_sample, per_sample_path)

    import json

    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    import yaml as _yaml

    snapshot_path = run_dir / "config_snapshot.yaml"
    snapshot = {
        "effective_config": config_snapshot.get("effective_config"),
        "audit": {
            "config_fingerprint": config_fingerprint,
            "fingerprint_overridden": config_fingerprint,
            "git_commit": get_git_commit(ROOT),
        },
    }
    snapshot_path.write_text(
        _yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    logger.log(f"[intent_smoke] wrote metrics, per_sample and config_snapshot to {run_dir}")
    logger.log("[intent_smoke] done")
    logger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

