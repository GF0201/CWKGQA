from __future__ import annotations

"""Rule-based, auditable IntentEngine for KGQA.

API (per question):
    predict(question: str) -> {
        "intents": [
            {
                "label": str,
                "score": float,  # 0..1 归一化
                "evidence_rules_triggered": [
                    {"rule_id": str, "weight": float}
                ],
            },
            ...
        ],
        "is_multi_intent": bool,
        "is_ambiguous": bool,
        "clarification_question": str | None,
        "clarification_options": list[str] | None,
    }

并提供审计信息：
    get_audit_info() -> {
        "rules_version_sha": str,
        "taxonomy_sha256": str,
        "thresholds": {...},
        "config_fingerprint_intent": str,
    }
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from framework.utils import ROOT  # type: ignore


INTENT_TAXONOMY_PATH = ROOT / "configs" / "intent_taxonomy.yaml"
INTENT_RULES_PATH = ROOT / "configs" / "intent_rules.yaml"


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass
class Rule:
    rule_id: str
    label: str
    weight: float
    keywords: List[str]
    regexes: List[re.Pattern]
    patterns: List[str]


class IntentEngine:
    """纯规则、多标签的意图识别模块（v1），可选融合可训练模型输出。"""

    def __init__(
        self,
        taxonomy_path: Path | None = None,
        rules_path: Path | None = None,
        use_model: bool = False,
        model_dir: Path | None = None,
    ) -> None:
        self.taxonomy_path = taxonomy_path or INTENT_TAXONOMY_PATH
        self.rules_path = rules_path or INTENT_RULES_PATH

        self.taxonomy_cfg = _load_yaml(self.taxonomy_path)
        self.rules_cfg = _load_yaml(self.rules_path)

        self.label_meta = self._build_label_meta(self.taxonomy_cfg)
        self.rules = self._build_rules(self.rules_cfg)
        self.thresholds = self.rules_cfg.get("thresholds", {}) or {}
        self.conflict_pairs = self._build_conflict_pairs(self.rules_cfg.get("conflict_matrix", []))
        self.clar_templates = self.rules_cfg.get("clarification_templates", {}) or {}

        # 可选：加载训练好的 TF-IDF + LR 模型（Task 20）
        self.model_dir = model_dir or (ROOT / "intent_workspace" / "artifacts")
        self.use_model = use_model
        self._model = None
        self._vectorizer = None
        self._model_label_order: List[str] | None = None
        if self.use_model:
            self._try_load_model()

        # 审计相关
        self.rules_sha = _sha256_file(self.rules_path)
        self.taxonomy_sha = _sha256_file(self.taxonomy_path)
        effective_cfg = {
            "taxonomy": self.taxonomy_cfg,
            "rules": self.rules_cfg,
            "thresholds": self.thresholds,
        }
        self.config_fingerprint = hashlib.sha256(
            _canonical_json(effective_cfg).encode("utf-8")
        ).hexdigest()

    # ---------- 公共 API ----------

    def predict(self, question: str) -> Dict[str, Any]:
        """对单个问题进行规则打分和多意图/歧义判定。"""

        q = (question or "").strip()
        if not q:
            return {
                "intents": [],
                "is_multi_intent": False,
                "is_ambiguous": False,
                "clarification_question": None,
                "clarification_options": None,
            }

        raw_scores: Dict[str, float] = {}
        rules_by_label: Dict[str, List[Dict[str, Any]]] = {}

        for r in self.rules:
            score_inc, fired = self._apply_rule(q, r)
            if not fired:
                continue
            raw_scores[r.label] = raw_scores.get(r.label, 0.0) + score_inc
            rules_by_label.setdefault(r.label, []).append(
                {"rule_id": r.rule_id, "weight": score_inc}
            )

        # 可选：模型打分
        model_scores: Dict[str, float] = {}
        if self._model is not None and self._vectorizer is not None and self._model_label_order:
            try:
                import numpy as np  # type: ignore

                X = self._vectorizer.transform([q])
                # 使用 decision_function（对 LR 等价于 margin），再做 sigmoid 归一化到 0..1
                decision = self._model.decision_function(X)
                if decision.ndim == 1:
                    scores_arr = decision
                else:
                    scores_arr = decision[0]
                scores_arr = 1.0 / (1.0 + np.exp(-scores_arr))
                for label, s in zip(self._model_label_order, scores_arr):
                    model_scores[label] = float(s)
            except Exception:
                # 模型异常时忽略模型分数，回退到纯规则
                model_scores = {}

        # 如规则完全未触发且没有模型分数，则视为 UNKNOWN
        if not raw_scores and not model_scores:
            intents: List[Dict[str, Any]] = [
                {
                    "label": "UNKNOWN",
                    "score": 0.0,
                    "evidence_rules_triggered": [],
                }
            ]
            return {
                "intents": intents,
                "is_multi_intent": False,
                "is_ambiguous": False,
                "clarification_question": None,
                "clarification_options": None,
            }

        # 规则与模型融合：score_final = alpha * rule + (1 - alpha) * model
        alpha = float(self.rules_cfg.get("model_fusion", {}).get("alpha_rule", 0.5))
        labels_union = set(raw_scores.keys()) | set(model_scores.keys())
        fused_scores: Dict[str, float] = {}
        for label in labels_union:
            r = raw_scores.get(label, 0.0)
            m = model_scores.get(label, 0.0)
            fused_scores[label] = alpha * r + (1.0 - alpha) * m

        # 如果没有启用模型或模型未加载成功，则 fused_scores 只等于 raw_scores
        if not model_scores and raw_scores:
            fused_scores = dict(raw_scores)

        # 归一化到 0..1：以当前问题的最大 fused_score 为 1.0
        max_score = max(fused_scores.values()) if fused_scores else 0.0
        norm_scores = {
            label: (score / max_score if max_score > 0 else 0.0)
            for label, score in fused_scores.items()
        }

        # 排序后的意图列表
        sorted_labels = sorted(
            norm_scores.items(), key=lambda kv: kv[1], reverse=True
        )
        intents: List[Dict[str, Any]] = []
        for label, score in sorted_labels:
            intents.append(
                {
                    "label": label,
                    "score": float(score),
                    "evidence_rules_triggered": rules_by_label.get(label, []),
                }
            )

        # 多意图 & 歧义判定
        is_multi, is_amb = self._decide_multi_and_ambiguous(sorted_labels)

        clar_q: str | None = None
        clar_opts: List[str] | None = None
        if is_amb:
            clar_q, clar_opts = self._make_clarification(sorted_labels)

        return {
            "intents": intents,
            "is_multi_intent": is_multi,
            "is_ambiguous": is_amb,
            "clarification_question": clar_q,
            "clarification_options": clar_opts,
        }

    def get_audit_info(self) -> Dict[str, Any]:
        """返回与本次配置相关的审计信息（可写入 metrics.audit / per-sample）。"""

        return {
            "rules_version_sha": self.rules_sha,
            "taxonomy_sha256": self.taxonomy_sha,
            "thresholds": {
                "multi_label_threshold": float(
                    self.thresholds.get("multi_label_threshold", 0.6)
                ),
                "ambiguous_margin": float(
                    self.thresholds.get("ambiguous_margin", 0.15)
                ),
                "min_confidence": float(
                    self.thresholds.get("min_confidence", 0.4)
                ),
            },
            "config_fingerprint_intent": self.config_fingerprint,
            "model_dir": str(self.model_dir),
        }

    # ---------- 内部工具 ----------

    @staticmethod
    def _build_label_meta(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        meta: Dict[str, Dict[str, Any]] = {}
        for item in cfg.get("intent_labels", []):
            name = str(item.get("name"))
            if not name:
                continue
            meta[name] = {
                "definition": item.get("definition", ""),
                "examples": item.get("examples", []),
                "negative_examples": item.get("negative_examples", []),
            }
        return meta

    @staticmethod
    def _build_conflict_pairs(raw_pairs: List[List[str]]) -> List[Tuple[str, str]]:
        pairs: List[Tuple[str, str]] = []
        for p in raw_pairs or []:
            if len(p) != 2:
                continue
            a, b = str(p[0]), str(p[1])
            pairs.append((a, b))
        return pairs

    @staticmethod
    def _build_rules(cfg: Dict[str, Any]) -> List[Rule]:
        rules: List[Rule] = []
        for raw in cfg.get("rules", []):
            rule_id = str(raw.get("id"))
            label = str(raw.get("label"))
            weight = float(raw.get("weight", 1.0))
            keywords = [str(k) for k in raw.get("keywords", [])]
            regexes = [
                re.compile(pat) for pat in raw.get("regex", []) + raw.get("regexes", [])
            ]
            patterns = [str(p) for p in raw.get("patterns", [])]
            rules.append(
                Rule(
                    rule_id=rule_id,
                    label=label,
                    weight=weight,
                    keywords=keywords,
                    regexes=regexes,
                    patterns=patterns,
                )
            )
        return rules

    def _try_load_model(self) -> None:
        """Best-effort load of trained intent model and vectorizer."""

        try:
            import joblib  # type: ignore
        except Exception:
            return

        vec_path = self.model_dir / "intent_vectorizer.pkl"
        model_path = self.model_dir / "intent_model.pkl"
        manifest_path = self.model_dir / "intent_training_manifest.json"
        if not (vec_path.exists() and model_path.exists() and manifest_path.exists()):
            return

        try:
            self._vectorizer = joblib.load(vec_path)
            self._model = joblib.load(model_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._model_label_order = list(manifest.get("label_order") or [])
        except Exception:
            self._vectorizer = None
            self._model = None
            self._model_label_order = None

    @staticmethod
    def _apply_rule(question: str, rule: Rule) -> Tuple[float, bool]:
        """对单条规则进行匹配，返回 (得分增量, 是否触发)。"""

        q = question
        fired = False

        # 关键词：简单子串匹配
        for kw in rule.keywords:
            if kw and kw in q:
                fired = True
                break

        # patterns：同样视作子串匹配
        if not fired:
            for pat in rule.patterns:
                if pat and pat in q:
                    fired = True
                    break

        # 正则：只要任一 pattern 命中即可
        if not fired:
            for rgx in rule.regexes:
                if rgx.search(q):
                    fired = True
                    break

        if not fired:
            return 0.0, False

        return rule.weight, True

    def _decide_multi_and_ambiguous(
        self,
        sorted_labels: List[Tuple[str, float]],
    ) -> Tuple[bool, bool]:
        """根据归一化分数和阈值判断多意图/歧义。"""

        multi_th = float(self.thresholds.get("multi_label_threshold", 0.6))
        amb_margin = float(self.thresholds.get("ambiguous_margin", 0.15))
        min_conf = float(self.thresholds.get("min_confidence", 0.4))

        scores = [s for _, s in sorted_labels]
        labels = [l for l, _ in sorted_labels]

        # 多意图：达到 multi_th 的标签数 >= 2
        n_active = sum(1 for s in scores if s >= multi_th)
        is_multi = n_active >= 2

        if not scores:
            return False, False

        top1 = scores[0]
        top1_label = labels[0]
        top2 = scores[1] if len(scores) > 1 else 0.0
        top2_label = labels[1] if len(labels) > 1 else None

        is_amb = False

        # 条件 1：top1 - top2 差距很小
        if len(scores) > 1 and (top1 - top2) <= amb_margin:
            is_amb = True

        # 条件 2：整体置信度不足
        if top1 < min_conf:
            is_amb = True

        # 条件 3：命中 conflict_matrix 且分差小
        if top2_label is not None:
            pair = (top1_label, top2_label)
            pair_rev = (top2_label, top1_label)
            if pair in self.conflict_pairs or pair_rev in self.conflict_pairs:
                if abs(top1 - top2) <= amb_margin:
                    is_amb = True

        return is_multi, is_amb

    def _make_clarification(
        self,
        sorted_labels: List[Tuple[str, float]],
    ) -> Tuple[str | None, List[str] | None]:
        """根据 top2~top3 标签生成澄清问题与候选选项。"""

        if not sorted_labels:
            return None, None

        # 取前 3 个非零分数的标签作为候选
        candidates = [lab for lab, sc in sorted_labels if sc > 0][:3]
        if not candidates:
            return None, None

        # 优先针对前 2 个标签查找特定模板
        clar_q: str | None = None
        if len(candidates) >= 2:
            a, b = candidates[0], candidates[1]
            key1 = f"{a}_vs_{b}"
            key2 = f"{b}_vs_{a}"
            if key1 in self.clar_templates:
                clar_q = self.clar_templates[key1]
            elif key2 in self.clar_templates:
                clar_q = self.clar_templates[key2]

        # 否则使用 generic 模板
        if clar_q is None:
            generic = self.clar_templates.get("generic")
            if generic:
                clar_q = generic.replace("{candidates}", ", ".join(candidates))

        if clar_q is None:
            return None, None

        return clar_q, candidates


__all__ = ["IntentEngine"]

