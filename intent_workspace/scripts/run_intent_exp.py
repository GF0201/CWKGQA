#!/usr/bin/env python3
"""Unified entrypoint for intent_workspace experiments.

Modes:
    --mode rule_predict
        - 读取输入数据与 intent 配置
        - 调用 intent_workspace.src.intent_engine.run_rule_predict
        - 写出 per-run 必需文件：
            A) repro_manifest.json
            B) config_snapshot.yaml
            C) metrics.json
            D) per_sample_intent_results.jsonl
            E) run.log
            F) summary.md
        - 运行结束后检查上述文件是否全部存在，缺失则 exit non-zero。

    --mode report  (可选增强)
        - 基于已有 per-sample 结果或重新运行 rule_predict 做补充报告（当前实现为 no-op 占位）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is on sys.path so that `core` and other top-level
# modules can be imported correctly when running this script directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core import DualLogger, write_repro_manifest, save_jsonl  # type: ignore

from intent_workspace.src.intent_engine import run_rule_predict  # type: ignore
from intent_workspace.src.utils import ROOT, get_git_commit  # type: ignore


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _update_metrics_audit(
    metrics: Dict[str, Any],
    *,
    config_fingerprint: str,
    input_path: Path,
    run_dir: Path,
) -> None:
    audit = metrics.setdefault("audit", {})
    audit["config_fingerprint"] = config_fingerprint
    audit["input_path"] = str(input_path)
    try:
        audit["input_hash"] = _sha256_file(input_path)
    except Exception:
        audit["input_hash"] = None
    audit["run_dir"] = str(run_dir)


def _write_summary_md(
    path: Path,
    *,
    run_id: str,
    mode: str,
    metrics: Dict[str, Any],
    config_fingerprint: str,
) -> None:
    overall = metrics.get("overall", {}) or {}
    macro_f1 = overall.get("macro_f1")
    micro_f1 = overall.get("micro_f1")
    amb_rate = overall.get("ambiguous_rate")
    multi_rate = overall.get("multi_intent_rate")
    cov_rate = overall.get("coverage_rate")

    lines: List[str] = []
    lines.append(f"# Intent run summary: {run_id}")
    lines.append("")
    lines.append(f"- Mode: `{mode}`")
    lines.append(f"- Config fingerprint: `{config_fingerprint}`")
    lines.append(
        f"- Macro F1 / Micro F1: {macro_f1!r} / {micro_f1!r} (may be null if no gold intents)"
    )
    lines.append(
        f"- Ambiguous rate / multi-intent rate / coverage rate: {amb_rate:.3f} / {multi_rate:.3f} / {cov_rate:.3f}"
    )
    lines.append("- Notes: 此 run 仅为规则版意图识别基线，可用于后续模型/规则改进对比。")

    path.write_text("\n".join(lines), encoding="utf-8")


def _append_index(
    *,
    run_id: str,
    mode: str,
    run_dir: Path,
    metrics: Dict[str, Any],
    config_fingerprint: str,
    input_path: Path,
    index_path: Path,
) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    overall = metrics.get("overall", {}) or {}
    entry = {
        "run_id": run_id,
        "datetime": datetime.now().isoformat(),
        "mode": mode,
        "config_fingerprint": config_fingerprint,
        "input_path": str(input_path),
        "input_hash": _sha256_file(input_path) if input_path.exists() else None,
        "key_metrics": {
            "macro_f1": overall.get("macro_f1"),
            "ambiguous_rate": overall.get("ambiguous_rate"),
            "multi_intent_rate": overall.get("multi_intent_rate"),
        },
        "notes": "",
    }
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _check_required_files(run_dir: Path) -> List[str]:
    required = [
        "repro_manifest.json",
        "config_snapshot.yaml",
        "metrics.json",
        "per_sample_intent_results.jsonl",
        "run.log",
        "summary.md",
    ]
    missing: List[str] = []
    for name in required:
        if not (run_dir / name).exists():
            missing.append(name)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Intent workspace experiment runner")
    parser.add_argument(
        "--mode",
        type=str,
        required=True,
        choices=["rule_predict", "report"],
        help="Experiment mode: rule_predict / report.",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Input JSONL path; default from intent_experiment_defaults.yaml.",
    )
    parser.add_argument(
        "--run_id",
        type=str,
        default=None,
        help="Run id; default: intent_YYYYMMDD_HHMMSS_rule_v1",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="intent_workspace/configs/intent_experiment_defaults.yaml",
        help="Defaults YAML for intent experiments.",
    )
    args = parser.parse_args()

    defaults_path = (ROOT / args.config) if not Path(args.config).is_absolute() else Path(args.config)
    if not defaults_path.exists():
        print(f"Defaults config not found: {defaults_path}", file=sys.stderr)
        return 1

    import yaml

    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8")) or {}
    input_rel = args.input or defaults.get("default_input_path", "datasets/domain_main_qa/test.jsonl")
    input_path = (ROOT / input_rel) if not Path(input_rel).is_absolute() else Path(input_rel)
    if not input_path.exists():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 1

    output_base_rel = defaults.get("output_base_dir", "intent_workspace/runs")
    output_base = ROOT / output_base_rel
    output_base.mkdir(parents=True, exist_ok=True)

    run_id = args.run_id or f"intent_{datetime.now().strftime('%Y%m%d_%H%M%S')}_rule_v1"
    run_dir = _ensure_dir(output_base / run_id)

    logger = DualLogger(run_dir, "run.log")
    start_time = datetime.now().isoformat()
    logger.log(f"[intent] run_id={run_id}")
    logger.log(f"[intent] mode={args.mode}")
    logger.log(f"[intent] input={input_path}")
    logger.log(f"[intent] defaults={defaults_path}")

    if args.mode == "rule_predict":
        metrics, per_sample, config_snapshot, config_fingerprint = run_rule_predict(
            project_root=ROOT,
            input_path=input_path,
            defaults_path=defaults_path,
            run_dir=run_dir,
            logger=logger,
        )

        # 写 per-sample 结果
        per_sample_path = run_dir / "per_sample_intent_results.jsonl"
        save_jsonl(per_sample, per_sample_path)
        logger.log(f"[intent] wrote {per_sample_path}")

        # 写 metrics.json（带 audit）
        _update_metrics_audit(
            metrics,
            config_fingerprint=config_fingerprint,
            input_path=input_path,
            run_dir=run_dir,
        )
        metrics_path = run_dir / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.log(f"[intent] wrote {metrics_path}")

        # 写 config_snapshot.yaml
        import yaml as _yaml

        snapshot = {
            "effective_config": config_snapshot.get("effective_config"),
            "audit": {
                "config_fingerprint": config_fingerprint,
                "fingerprint_overridden": config_fingerprint,
                "git_commit": get_git_commit(ROOT),
            },
        }
        snapshot_path = run_dir / "config_snapshot.yaml"
        snapshot_path.write_text(_yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False), encoding="utf-8")
        logger.log(f"[intent] wrote {snapshot_path}")

        # 写 summary.md
        summary_path = run_dir / "summary.md"
        _write_summary_md(
            summary_path,
            run_id=run_id,
            mode=args.mode,
            metrics=metrics,
            config_fingerprint=config_fingerprint,
        )
        logger.log(f"[intent] wrote {summary_path}")

        # 写 repro_manifest.json
        end_time = datetime.now().isoformat()
        manifest = write_repro_manifest(
            run_dir,
            run_id=run_id,
            start_time=start_time,
            end_time=end_time,
            command_argv=sys.argv,
            seed=int(defaults.get("seed", 42)),
            inputs=[input_path, defaults_path],
            config_dict=snapshot.get("effective_config") or {},
            args={
                "mode": args.mode,
                "input": str(input_path),
                "config": str(defaults_path),
            },
            warnings=[],
            old_dir=None,
            data_file=input_path,
            extra_fields={
                "phase": "intent_rule_predict",
                "config_fingerprint": config_fingerprint,
                "git_commit": get_git_commit(ROOT),
            },
        )
        logger.log("[intent] wrote repro_manifest.json")
        logger.log(
            f"[intent] Inputs hashed: {len(manifest.get('input_files_sha256', {}))}; "
            f"first_keys={list(manifest.get('input_files_sha256', {}).keys())[:3]}"
        )

        # 校验必需文件
        missing = _check_required_files(run_dir)
        if missing:
            logger.log(f"[intent] MISSING required files: {missing}")
            logger.close()
            print(
                f"ERROR: run {run_id} missing required artifacts: {', '.join(missing)}",
                file=sys.stderr,
            )
            return 1

        # 更新 runs/_index/index.jsonl
        index_rel = defaults.get("report", {}).get(
            "index_path", "intent_workspace/runs/_index/index.jsonl"
        )
        index_path = ROOT / index_rel
        _append_index(
            run_id=run_id,
            mode=args.mode,
            run_dir=run_dir,
            metrics=metrics,
            config_fingerprint=config_fingerprint,
            input_path=input_path,
            index_path=index_path,
        )
        logger.log(f"[intent] appended index entry to {index_path}")

    else:
        # report 模式：当前实现为占位（可在后续版本中读取 per-sample 做更丰富统计）。
        logger.log("[intent] report mode currently does nothing (placeholder).")

    logger.log("[intent] done")
    logger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

