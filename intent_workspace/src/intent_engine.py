"""Rule-based intent engine for multi-intent / ambiguity / clarification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from core import DualLogger, load_jsonl

from .utils import build_effective_config, compute_config_fingerprint, load_intent_configs


@dataclass
class Rule:
    rule_id: str
    label: str
    weight: float
    patterns: List[str]


def _build_rules(rules_cfg: Dict[str, Any]) -> List[Rule]:
    rules: List[Rule] = []
    for raw in rules_cfg.get("rules", []):
        rules.append(
            Rule(
                rule_id=str(raw.get("id")),
                label=str(raw.get("label")),
                weight=float(raw.get("weight", 1.0)),
                patterns=[str(p) for p in raw.get("patterns", [])],
            )
        )
    return rules


def _apply_rules_to_question(
    question: str,
    rules: List[Rule],
) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
    """Apply all rules to a single question, return (label_scores, rules_fired)."""

    label_scores: Dict[str, float] = {}
    rules_fired: List[Dict[str, Any]] = []

    q = question or ""
    for r in rules:
        fired = any(pat in q for pat in r.patterns)
        if not fired:
            continue
        label_scores[r.label] = label_scores.get(r.label, 0.0) + r.weight
        rules_fired.append({"rule_id": r.rule_id, "label": r.label, "weight": r.weight})

    return label_scores, rules_fired


def _is_multi_intent(label_scores: Dict[str, float], threshold: float) -> bool:
    active = [s for s in label_scores.values() if s >= threshold]
    return len(active) > 1


def _is_ambiguous(label_scores: Dict[str, float], threshold: float) -> bool:
    return label_scores.get("AMBIGUOUS", 0.0) >= threshold


def _default_clarification(question: str) -> Tuple[str | None, List[str] | None]:
    # 简单占位实现：真实系统可生成更细致的澄清问句与选项
    if not question:
        return None, None
    return f"请问您希望澄清关于“{question[:30]}”的哪一方面？", []


def run_rule_predict(
    *,
    project_root: Path,
    input_path: Path,
    defaults_path: Path,
    run_dir: Path,
    logger: DualLogger,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], str]:
    """Main entry for rule-based intent prediction.

    Returns:
        metrics: 聚合指标字典（见 artifacts_schema）
        per_sample: per-sample 结果列表
        config_snapshot: 用于写入 config_snapshot.yaml 的快照字典
        config_fingerprint: 配置指纹（SHA256）
    """

    logger.log(f"[intent] loading configs from {defaults_path}")
    defaults, taxonomy_cfg, rules_cfg = load_intent_configs(defaults_path)
    rules = _build_rules(rules_cfg)

    thresholds = defaults.get("thresholds", {})
    th_multi = float(thresholds.get("multi_intent", 0.5))
    th_ambiguous = float(thresholds.get("ambiguous", 0.5))

    effective_config = build_effective_config(
        defaults=defaults,
        taxonomy=taxonomy_cfg,
        rules=rules_cfg,
        cli_overrides={},  # 当前实现无 CLI 覆盖，预留字段
    )
    config_fingerprint, _canonical = compute_config_fingerprint(effective_config)

    logger.log(f"[intent] config_fingerprint={config_fingerprint}")

    # Load dataset
    logger.log(f"[intent] loading input data from {input_path}")
    samples = list(load_jsonl(input_path))
    n = len(samples)
    logger.log(f"[intent] loaded {n} samples")

    per_sample: List[Dict[str, Any]] = []
    n_any_rule = 0
    n_ambiguous = 0
    n_multi_intent = 0

    for s in samples:
        qid = s.get("id", "")
        question = str(s.get("question", ""))

        label_scores, rules_fired = _apply_rules_to_question(question, rules)
        if rules_fired:
            n_any_rule += 1

        is_multi = _is_multi_intent(label_scores, th_multi)
        is_amb = _is_ambiguous(label_scores, th_ambiguous)

        if is_multi:
            n_multi_intent += 1
        if is_amb:
            n_ambiguous += 1

        # 排序后的预测列表
        pred_intents = [
            {"label": label, "score": score}
            for label, score in sorted(label_scores.items(), key=lambda kv: kv[1], reverse=True)
        ]

        clarification_question = None
        clarification_options: List[str] | None = None
        if is_amb:
            clarification_question, clarification_options = _default_clarification(question)

        record = {
            "id": qid,
            "question": question,
            "gold_intents": None,  # 当前版本默认无 gold，可后续扩展
            "pred_intents": pred_intents,
            "is_multi_intent": is_multi,
            "is_ambiguous": is_amb,
            "clarification_question": clarification_question,
            "clarification_options": clarification_options,
            "rules_fired": rules_fired,
            "thresholds_used": {
                "multi_intent": th_multi,
                "ambiguous": th_ambiguous,
            },
        }
        per_sample.append(record)

    coverage_rate = float(n_any_rule) / n if n > 0 else 0.0
    ambiguous_rate = float(n_ambiguous) / n if n > 0 else 0.0
    multi_intent_rate = float(n_multi_intent) / n if n > 0 else 0.0

    # 当前无 gold，因此宏/微 F1、multi_intent_accuracy 统一置为 null
    metrics: Dict[str, Any] = {
        "overall": {
            "macro_f1": None,
            "micro_f1": None,
            "multi_intent_accuracy": None,
            "ambiguous_rate": ambiguous_rate,
            "multi_intent_rate": multi_intent_rate,
            "coverage_rate": coverage_rate,
        },
        "per_label": {},  # 如后续有 gold，可在此填充分标签指标
        "rule_stats": {
            "n_samples": n,
            "n_with_any_rule": n_any_rule,
        },
        "audit": {
            # config_fingerprint / input_hash 等由上层脚本补充
        },
    }

    config_snapshot = {
        "effective_config": effective_config,
        "audit": {
            "config_fingerprint": config_fingerprint,
            "fingerprint_overridden": config_fingerprint,
        },
    }

    return metrics, per_sample, config_snapshot, config_fingerprint

