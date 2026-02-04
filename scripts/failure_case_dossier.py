#!/usr/bin/env python3
"""Generate failure-case dossiers for specific ids in a guardrail run.

Usage example:
  python scripts/failure_case_dossier.py \
    --run_dir runs/exp_guardrail_evidence_bounded_v2_bm25_k10_real_v1 \
    --ids draft_25 draft_40

Outputs:
  <run_dir>/artifacts/failure_case_dossier.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framework.eval import normalize_answer, mixed_segmentation  # type: ignore
from framework.evidence_support import parse_contract, compute_support  # type: ignore

EVIDENCE_KEY_TOKENS_K = 5


def _compute_support_detail(
    raw_answer: str,
    evidence_ids: List[int],
    retrieved: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return detailed evidence support info based on unified support module."""
    support = compute_support(raw_answer, evidence_ids, retrieved, key_tokens_k=EVIDENCE_KEY_TOKENS_K)
    return {
        "key_tokens": support.get("key_tokens", []),
        "covered_tokens": support.get("covered_tokens", []),
        "uncovered_tokens": support.get("missing_tokens", []),
        "coverage": support.get("coverage"),
    }


def _classify_cause(
    question: str,
    gold: str,
    raw_pred: str,
    final_pred: str,
    retrieved: List[Dict[str, Any]],
    support_detail: Dict[str, Any],
) -> str:
    """Heuristic classification into A/B/C/D."""
    coverage = support_detail.get("coverage")
    key_tokens = support_detail.get("key_tokens") or []

    # A: Retriever miss – no relevant tokens in any triple and F1=0
    all_ctx = " ".join(
        f"{t.get('subject','')} {t.get('predicate','')} {t.get('object','')}"
        for t in retrieved
    )
    ctx_tokens = set(mixed_segmentation(normalize_answer(all_ctx)))
    gold_tokens = mixed_segmentation(normalize_answer(gold))
    gold_in_ctx = any(t in ctx_tokens for t in gold_tokens)

    if not gold_in_ctx:
        return "A"  # triples 不含答案

    # If gold clearly in ctx but evidence_ids empty or misaligned -> B
    if coverage is None or coverage < 0.5:
        return "B"  # evidence 选错

    # If coverage high but eval为0 或很低，可能是同义或 tokenize 问题 -> C/D
    if coverage >= 0.5 and key_tokens:
        # 简单启发：答案与 gold 在规范化后 Jaccard 很小则偏向 D（gold 口径/同义）
        pred_tokens = set(mixed_segmentation(normalize_answer(final_pred)))
        gold_set = set(gold_tokens)
        inter = len(pred_tokens & gold_set)
        union = len(pred_tokens | gold_set) or 1
        jacc = inter / union
        if jacc < 0.3:
            return "D"
        return "C"

    return "D"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", type=str, required=True)
    parser.add_argument("--ids", type=str, nargs="+", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    artifacts_dir = run_dir / "artifacts"
    per_sample_path = artifacts_dir / "per_sample_results.jsonl"
    if not per_sample_path.exists():
        raise SystemExit(f"Missing {per_sample_path}")

    rows: List[Dict[str, Any]] = []
    with per_sample_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    target_ids = set(args.ids)
    selected = [r for r in rows if str(r.get("id")) in target_ids]

    dossier: Dict[str, Any] = {}
    for s in selected:
        sid = str(s.get("id"))
        question = s.get("question", "")
        gold_list = s.get("gold_answers") or []
        gold = gold_list[0] if gold_list else ""
        raw_pred = (s.get("raw_prediction") or "").strip()
        final_pred = (s.get("prediction") or "").strip()
        retrieved = s.get("retrieved_triples") or []
        evidence_ids = s.get("evidence_line_ids") or []

        # 统一使用两行合同解析得到 raw_answer，避免 "ANSWER:" 前缀污染
        parsed = parse_contract(raw_pred or final_pred, retrieved_k=len(retrieved))
        raw_answer = parsed.raw_answer

        support_detail = _compute_support_detail(
            raw_answer or final_pred,
            evidence_ids,
            retrieved,
        )
        cause = _classify_cause(
            question,
            gold,
            raw_pred,
            final_pred,
            retrieved,
            support_detail,
        )

        dossier[sid] = {
            "question": question,
            "gold": gold,
            "raw_prediction_before_enforcement": raw_pred,
            "final_prediction": final_pred,
            "retrieved_triples": retrieved,
            "evidence_line_ids": evidence_ids,
            "evidence_support_detail": support_detail,
            "attribution": cause,
        }

    out_path = artifacts_dir / "failure_case_dossier.json"
    out_path.write_text(json.dumps(dossier, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

