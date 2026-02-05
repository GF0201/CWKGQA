#!/usr/bin/env python3
"""Collect mainline KGQA runs and materialize intent_workspace-style runs.

用途（P0）：
- 读取主线 `runs/<run_id>/` 下的工件（特别是 `metrics.json` 与 `artifacts/per_sample_results.jsonl`）；
- 校验主线运行是否满足“默认真实配置指纹 + Guardrail v2 Policy R + BM25 k=10”的约束；
- 基于主线 per-sample 中的 `intent_pred` / `intent_audit` 字段，生成：
    - intent_workspace 规范的 `per_sample_intent_results.jsonl`
    - intent 视角的 `metrics.json`（聚合指标 + 审计字段）
    - `config_snapshot.yaml`（主线默认配置 + intent 配置快照）
    - `repro_manifest.json`（引用主线 manifest 并补充元数据）
    - `run.log` / `summary.md`
- 将上述工件写入 `intent_workspace/runs/<run_id_intent>/`，并更新
  `intent_workspace/runs/_index/index.jsonl`。

每个 intent_workspace 视角的 run 会被视作一次“基于主线 run 的 intent 分析实验”，
满足 artifacts_schema.md 中 A–F 的最小要求，并在缺失任何必需工件时 fail-fast。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 确保可以导入顶层模块（core / framework 等）
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core import DualLogger, write_repro_manifest  # type: ignore
from framework.utils import RUNS_DIR, ensure_dir, load_jsonl  # type: ignore

from intent_workspace.src.utils import ROOT, get_git_commit  # type: ignore


# 根据题述要求锁定的主线默认配置指纹（由 default_real_bm25_k10_evidence_guardrail_v2.yaml 计算）
DEFAULT_MAIN_CONFIG_FINGERPRINT = (
    "51396c02d84be88640a30208233ed487eae614f1dc1be52d5d62ef0f399e45a3"
)


def _sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _check_required_files(run_dir: Path) -> List[str]:
    """意图工作区规范：A–F 六个工件缺一不可。"""
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


def _derive_intent_per_sample_rows(
    per_sample_main: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """从主线 per-sample 结果构造 intent_workspace 规范的 per-sample 行。

    返回：
    - rows_intent: 写入 per_sample_intent_results.jsonl 的行列表
    - rates: {"ambiguous_rate": float, "multi_intent_rate": float, "coverage_rate": float}
    """

    rows_intent: List[Dict[str, Any]] = []
    n = len(per_sample_main)
    n_amb = 0
    n_multi = 0
    n_with_any_intent = 0

    for row in per_sample_main:
        sid = row.get("id")
        q = row.get("question") or ""
        intent_pred = row.get("intent_pred") or {}
        intent_audit = row.get("intent_audit") or {}

        intents = intent_pred.get("intents") or []
        is_multi = bool(intent_pred.get("is_multi_intent"))
        is_amb = bool(intent_pred.get("is_ambiguous"))
        clar_q = intent_pred.get("clarification_question")
        clar_opts = intent_pred.get("clarification_options")

        if intents:
            n_with_any_intent += 1
        if is_multi:
            n_multi += 1
        if is_amb:
            n_amb += 1

        # 展平所有触发规则，带上目标 label 方便后续 slice
        rules_fired: List[Dict[str, Any]] = []
        for it in intents:
            label = it.get("label")
            for ev in it.get("evidence_rules_triggered") or []:
                rid = ev.get("rule_id")
                weight = ev.get("weight")
                rules_fired.append(
                    {"rule_id": rid, "label": label, "weight": float(weight or 0.0)}
                )

        thresholds_used = intent_audit.get("thresholds") or {}

        row_intent: Dict[str, Any] = {
            "id": sid,
            "question": q,
            "gold_intents": None,  # P0 阶段无显式 gold
            "pred_intents": intents,
            "is_multi_intent": is_multi,
            "is_ambiguous": is_amb,
            "clarification_question": clar_q,
            "clarification_options": clar_opts,
            "rules_fired": rules_fired,
            "thresholds_used": thresholds_used,
        }
        rows_intent.append(row_intent)

    rates = {
        "ambiguous_rate": (n_amb / n) if n else 0.0,
        "multi_intent_rate": (n_multi / n) if n else 0.0,
        "coverage_rate": (n_with_any_intent / n) if n else 0.0,
    }
    return rows_intent, rates


def _build_intent_metrics(
    per_sample_intent: List[Dict[str, Any]],
    *,
    intent_cfg_fp: str | None,
    input_path: Path,
    run_dir: Path,
) -> Dict[str, Any]:
    """构造 intent_workspace 视角的 metrics.json。

    - 无 gold 时：macro/micro F1 置为 null，仅给出歧义率、多意图率与覆盖率。
    """

    n = len(per_sample_intent)
    n_amb = 0
    n_multi = 0
    n_with_any = 0
    per_label_counts: Dict[str, int] = {}

    for r in per_sample_intent:
        intents = r.get("pred_intents") or []
        if intents:
            n_with_any += 1
            top_label = intents[0].get("label")
            if top_label is not None:
                per_label_counts[str(top_label)] = per_label_counts.get(str(top_label), 0) + 1
        if r.get("is_ambiguous"):
            n_amb += 1
        if r.get("is_multi_intent"):
            n_multi += 1

    ambiguous_rate = n_amb / n if n else 0.0
    multi_rate = n_multi / n if n else 0.0
    coverage_rate = n_with_any / n if n else 0.0

    per_label: Dict[str, Any] = {}
    for label, cnt in per_label_counts.items():
        per_label[label] = {
            "precision": None,
            "recall": None,
            "f1": None,
            "support": cnt,
        }

    metrics: Dict[str, Any] = {
        "overall": {
            "macro_f1": None,
            "micro_f1": None,
            "multi_intent_accuracy": None,
            "ambiguous_rate": ambiguous_rate,
            "multi_intent_rate": multi_rate,
            "coverage_rate": coverage_rate,
        },
        "per_label": per_label,
        "rule_stats": {
            "n_samples": n,
            "n_with_any_rule": sum(
                1 for r in per_sample_intent if (r.get("rules_fired") or [])
            ),
        },
        "audit": {
            # 对齐 artifacts_schema：此处采用 intent 配置指纹，
            # 同时在 config_snapshot.yaml 中给出主线配置指纹。
            "config_fingerprint": intent_cfg_fp,
            "input_path": str(input_path),
            "input_hash": _sha256_file(input_path) if input_path.exists() else None,
            "git_commit": get_git_commit(ROOT),
            "derived_from": str(run_dir),
        },
    }
    return metrics


def _append_index(
    *,
    run_id: str,
    mode: str,
    run_dir: Path,
    metrics: Dict[str, Any],
    config_fingerprint: str | None,
    input_path: Path,
    index_path: Path,
) -> None:
    """向 intent_workspace 索引文件追加一行记录。"""

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
            "ambiguous_rate": overall.get("ambiguous_rate"),
            "multi_intent_rate": overall.get("multi_intent_rate"),
            "coverage_rate": overall.get("coverage_rate"),
        },
        "notes": "from_mainline_baseline",
    }
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect mainline runs and materialize intent_workspace-style runs."
    )
    parser.add_argument(
        "--runs",
        nargs="+",
        required=True,
        help="Mainline run ids under runs/ to collect (e.g. exp_default_intent_none_real_v1 ...).",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default="default_guardrail_v2_policyR",
        help="Short tag used in generated intent_workspace run_id, e.g. default_guardrail_v2_policyR.",
    )
    args = parser.parse_args()

    ws_runs_base = ROOT / "intent_workspace" / "runs"
    ws_runs_base.mkdir(parents=True, exist_ok=True)

    for base_run_id in args.runs:
        main_run_dir = RUNS_DIR / base_run_id
        if not main_run_dir.exists():
            print(f"[collect] ERROR: main run dir not found: {main_run_dir}", file=sys.stderr)
            return 1

        metrics_path = main_run_dir / "metrics.json"
        per_sample_path = main_run_dir / "artifacts" / "per_sample_results.jsonl"
        manifest_path = main_run_dir / "repro_manifest.json"

        if not metrics_path.exists() or not per_sample_path.exists() or not manifest_path.exists():
            print(
                f"[collect] ERROR: main run {base_run_id} missing required source files "
                f"(metrics.json / artifacts/per_sample_results.jsonl / repro_manifest.json)",
                file=sys.stderr,
            )
            return 1

        metrics_main = _load_json(metrics_path)
        audit_main = metrics_main.get("audit", {}) or {}

        # 1) 主线配置约束检查：默认指纹 + Guardrail v2 Policy R + BM25 k=10
        cfg_fp = audit_main.get("config_fingerprint")
        if cfg_fp != DEFAULT_MAIN_CONFIG_FINGERPRINT:
            print(
                f"[collect] ERROR: main run {base_run_id} has config_fingerprint={cfg_fp!r}, "
                f"expected {DEFAULT_MAIN_CONFIG_FINGERPRINT}",
                file=sys.stderr,
            )
            return 1

        if audit_main.get("contract_variant") != "answer_plus_evidence_guardrail_v2":
            print(
                f"[collect] ERROR: main run {base_run_id} contract_variant="
                f"{audit_main.get('contract_variant')!r} is not 'answer_plus_evidence_guardrail_v2'",
                file=sys.stderr,
            )
            return 1

        if audit_main.get("enforcement_policy") != "retry_once_if_support_lt_0.5_else_force_unknown":
            print(
                f"[collect] ERROR: main run {base_run_id} enforcement_policy="
                f"{audit_main.get('enforcement_policy')!r} is not "
                "'retry_once_if_support_lt_0.5_else_force_unknown'",
                file=sys.stderr,
            )
            return 1

        if audit_main.get("retriever_type") != "bm25" or int(audit_main.get("retriever_topk", 0)) != 10:
            print(
                f"[collect] ERROR: main run {base_run_id} retriever_type/topk="
                f"{audit_main.get('retriever_type')!r}/{audit_main.get('retriever_topk')!r} "
                "is not bm25/10",
                file=sys.stderr,
            )
            return 1

        intent_mode = audit_main.get("intent_mode") or "none"
        intent_cfg_fp = audit_main.get("intent_config_fingerprint")

        # 2) 生成 intent_workspace run_id 与目录
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_tag = f"{args.tag}_{intent_mode}"
        intent_run_id = f"intent_{ts}_{short_tag}"
        intent_run_dir = ensure_dir(ws_runs_base / intent_run_id)

        logger = DualLogger(intent_run_dir, "run.log")
        logger.log(f"[collect] intent_run_id={intent_run_id}")
        logger.log(f"[collect] source_main_run={base_run_id}")
        logger.log(f"[collect] main_run_dir={main_run_dir}")
        logger.log(f"[collect] intent_mode={intent_mode}")

        start_time = datetime.now().isoformat()

        per_sample_main = load_jsonl(per_sample_path)
        logger.log(f"[collect] loaded {len(per_sample_main)} per-sample rows from mainline run")

        # 3) 构造 per-sample intent 结果
        per_sample_intent, _ = _derive_intent_per_sample_rows(per_sample_main)

        # 4) 构造 metrics.json（intent 视角）
        manifest_main = _load_json(manifest_path)
        input_files = manifest_main.get("input_files_sha256") or {}
        # 优先从 manifest 中找 test 数据路径；否则回退到 metrics.audits 的 retriever 输入。
        input_path = None
        for key in input_files.keys():
            if "test" in key.lower():
                input_path = key
                break
        # best effort: 如果 key 不是路径而是逻辑名，可以回退到 repro_manifest 的 data_file 字段
        data_file = manifest_main.get("data_file")
        if isinstance(data_file, str):
            input_path_resolved = Path(data_file)
        elif input_path:
            input_path_resolved = Path(input_path)
        else:
            # 最保守：使用 metrics.json 所在目录附近的默认 test 路径
            input_path_resolved = ROOT / "datasets" / "domain_main_qa" / "test.jsonl"

        metrics_intent = _build_intent_metrics(
            per_sample_intent,
            intent_cfg_fp=intent_cfg_fp,
            input_path=input_path_resolved,
            run_dir=intent_run_dir,
        )

        # 5) 写 per_sample_intent_results.jsonl
        ps_intent_path = intent_run_dir / "per_sample_intent_results.jsonl"
        with open(ps_intent_path, "w", encoding="utf-8") as f:
            for r in per_sample_intent:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        logger.log(f"[collect] wrote {ps_intent_path}")

        # 6) 写 metrics.json
        metrics_intent_path = intent_run_dir / "metrics.json"
        metrics_intent_path.write_text(
            json.dumps(metrics_intent, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.log(f"[collect] wrote {metrics_intent_path}")

        # 7) 写 config_snapshot.yaml（最小化但包含主线与 intent 审计信息）
        import yaml  # type: ignore

        snapshot = {
            "effective_config": {
                "main_default_config_fingerprint": DEFAULT_MAIN_CONFIG_FINGERPRINT,
                "intent_config_fingerprint": intent_cfg_fp,
                "intent_thresholds": audit_main.get("intent_thresholds"),
                "intent_rules_sha": audit_main.get("intent_rules_sha"),
                "intent_taxonomy_sha": audit_main.get("intent_taxonomy_sha"),
            },
            "audit": {
                "config_fingerprint": intent_cfg_fp,
                "fingerprint_overridden": intent_cfg_fp,
                "git_commit": get_git_commit(ROOT),
                "derived_from_main_run": base_run_id,
            },
        }
        snapshot_path = intent_run_dir / "config_snapshot.yaml"
        snapshot_path.write_text(
            yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        logger.log(f"[collect] wrote {snapshot_path}")

        # 8) 写 summary.md（人类可读摘要）
        summary_path = intent_run_dir / "summary.md"
        overall = metrics_intent.get("overall", {}) or {}
        lines: List[str] = []
        lines.append(f"# Intent-from-mainline summary: {intent_run_id}")
        lines.append("")
        lines.append(f"- Source mainline run: `{base_run_id}`")
        lines.append(f"- Intent mode: `{intent_mode}`")
        lines.append(
            "- Key rates: ambiguous_rate={:.3f}, multi_intent_rate={:.3f}, "
            "coverage_rate={:.3f}".format(
                overall.get("ambiguous_rate") or 0.0,
                overall.get("multi_intent_rate") or 0.0,
                overall.get("coverage_rate") or 0.0,
            )
        )
        lines.append(
            f"- Intent config fingerprint: `{intent_cfg_fp}` "
            f"(main default cfg fp: `{DEFAULT_MAIN_CONFIG_FINGERPRINT}`)"
        )
        lines.append(
            "- Notes: 此 run 由 collect_mainline_intent_runs.py 从主线 KGQA run 派生，"
            "仅用于 Intent 模块行为审计与对比分析，不直接改变主线结果。"
        )
        summary_path.write_text("\n".join(lines), encoding="utf-8")
        logger.log(f"[collect] wrote {summary_path}")

        # 9) 写 repro_manifest.json（基于主线 manifest 的轻量包装）
        end_time = datetime.now().isoformat()
        manifest_intent = write_repro_manifest(
            intent_run_dir,
            run_id=intent_run_id,
            start_time=start_time,
            end_time=end_time,
            command_argv=sys.argv,
            seed=int(audit_main.get("seed", 42)),
            inputs=[input_path_resolved],
            config_dict=snapshot.get("effective_config") or {},
            args={
                "mode": "from_mainline",
                "source_run_id": base_run_id,
                "intent_mode": intent_mode,
            },
            warnings=[],
            old_dir=None,
            data_file=input_path_resolved,
            extra_fields={
                "phase": "intent_from_mainline",
                "config_fingerprint": intent_cfg_fp,
                "git_commit": get_git_commit(ROOT),
            },
        )
        logger.log("[collect] wrote repro_manifest.json")
        logger.log(
            f"[collect] Inputs hashed: {len(manifest_intent.get('input_files_sha256', {}))}; "
            f"first_keys={list(manifest_intent.get('input_files_sha256', {}).keys())[:3]}"
        )

        # 10) 校验必需工件
        missing = _check_required_files(intent_run_dir)
        if missing:
            logger.log(f"[collect] MISSING required files: {missing}")
            logger.close()
            print(
                f"ERROR: intent run {intent_run_id} missing required artifacts: {', '.join(missing)}",
                file=sys.stderr,
            )
            return 1

        # 11) 更新 intent_workspace 索引
        index_path = ROOT / "intent_workspace" / "runs" / "_index" / "index.jsonl"
        _append_index(
            run_id=intent_run_id,
            mode="from_mainline",
            run_dir=intent_run_dir,
            metrics=metrics_intent,
            config_fingerprint=intent_cfg_fp,
            input_path=input_path_resolved,
            index_path=index_path,
        )
        logger.log(f"[collect] appended index entry to {index_path}")

        logger.log("[collect] done for main run " + base_run_id)
        logger.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

