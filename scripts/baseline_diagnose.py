#!/usr/bin/env python3
"""Baseline diagnose pack: audit fingerprint, stats, error taxonomy, case study."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framework.eval import (  # type: ignore
    normalize_answer,
    mixed_segmentation,
    f1_score,
    exact_match_score,
    metric_max_over_ground_truths,
    evaluate_prediction,
)

GOLD_KEY_K = 5
GOLD_SHORT_THRESH = 15
PRED_LONG_THRESH = 30


def _sha256_file(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _load_jsonl(path: Path) -> list[dict]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def _ctx_tokens_from_triples(triples: list) -> list:
    parts = []
    for t in triples:
        s = t.get("subject") or t.get("head") or ""
        p = t.get("predicate") or t.get("connect") or ""
        o = t.get("object") or t.get("tail") or ""
        parts.append(f"{s} {p} {o}")
    return mixed_segmentation(normalize_answer(" ".join(parts)))


def _gold_token_hit_rate(gold: str, pred: str) -> float:
    gt = mixed_segmentation(normalize_answer(gold))
    pt = mixed_segmentation(normalize_answer(pred))
    if not gt:
        return 0.0
    common = Counter(gt) & Counter(pt)
    return sum(common.values()) / len(gt)


def _classify_label(
    retrieved: list,
    gold: str,
    pred: str,
    f1: float,
) -> str:
    ctx = set(_ctx_tokens_from_triples(retrieved))
    gold_tokens = mixed_segmentation(normalize_answer(gold))
    key_tokens = gold_tokens[:GOLD_KEY_K]
    key_in_ctx = any(t in ctx for t in key_tokens) if key_tokens else True

    retriever_miss = (not retrieved) or (key_tokens and not key_in_ctx)
    if retriever_miss:
        return "retriever_miss"

    gold_len = len(gold.strip())
    pred_len = len(pred.strip())

    if f1 == 0:
        return "ungrounded_or_wrong"

    if gold_len <= GOLD_SHORT_THRESH and pred_len >= PRED_LONG_THRESH and f1 > 0:
        return "format_mismatch"

    return "partial_correct"


def _quantile(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    i = int((len(s) - 1) * q)
    return s[min(i, len(s) - 1)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", type=str, default="runs/exp_baseline_20260203_230544")
    args = parser.parse_args()

    run_dir = ROOT / args.run_dir
    artifacts_dir = run_dir / "artifacts"
    per_sample_path = artifacts_dir / "per_sample_results.jsonl"
    if not per_sample_path.exists():
        print(f"Missing: {per_sample_path}", file=sys.stderr)
        return 1

    samples = _load_jsonl(per_sample_path)
    if not samples:
        print("No samples in per_sample_results.jsonl", file=sys.stderr)
        return 1

    # Recompute F1 with current eval
    for s in samples:
        pred = s.get("prediction") or ""
        golds = s.get("gold_answers") or []
        em, f1 = evaluate_prediction(pred, golds)
        s["_em"] = 1 if em else 0
        s["_f1"] = float(f1)

    # Step 1: Audit fingerprint
    eval_path = ROOT / "framework" / "eval.py"
    eval_sha = _sha256_file(eval_path) if eval_path.exists() else ""
    audit = {
        "eval_tokenizer": "mixed_zh_char_en_word_v1",
        "eval_py_sha256": eval_sha,
        "eval_remove_en_articles": True,
        "normalize_rules": "lower, remove_punc(en+cn), white_space_fix",
    }

    metrics_path = run_dir / "metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    else:
        metrics = {}
    metrics.setdefault("audit", {}).update(audit)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    # Step 2: Stats summary
    pred_lens = []
    gold_lens = []
    hit_rates = []
    f1s = []
    pred_tokens = []
    gold_tokens = []
    for s in samples:
        pred = (s.get("prediction") or "").strip()
        golds = s.get("gold_answers") or []
        gold = golds[0] if golds else ""
        pred_lens.append(len(pred))
        gold_lens.append(len(gold))
        hit_rates.append(_gold_token_hit_rate(gold, pred))
        f1s.append(s["_f1"])
        pred_tokens.append(len(mixed_segmentation(normalize_answer(pred))))
        gold_tokens.append(len(mixed_segmentation(normalize_answer(gold))))

    def mean(v): return sum(v) / len(v) if v else 0.0
    def med(v): return _quantile(v, 0.5)
    def p90(v): return _quantile(v, 0.9)

    len_hit = {
        "n": len(samples),
        "pred_len_char": {"mean": mean(pred_lens), "median": med(pred_lens), "p90": p90(pred_lens)},
        "gold_len_char": {"mean": mean(gold_lens), "median": med(gold_lens), "p90": p90(gold_lens)},
        "gold_token_hit_rate": {"mean": mean(hit_rates), "median": med(hit_rates)},
        "f1": {"mean": mean(f1s), "median": med(f1s), "p90": p90(f1s)},
        "pred_token_count": {"median": med(pred_tokens), "p90": p90(pred_tokens)},
        "gold_token_count": {"median": med(gold_tokens), "p90": p90(gold_tokens)},
    }
    (artifacts_dir / "baseline_len_hit_summary.json").write_text(
        json.dumps(len_hit, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Step 3: Error taxonomy
    taxonomy_rows = []
    label_counts = Counter()
    for s in samples:
        pred = (s.get("prediction") or "").strip()
        golds = s.get("gold_answers") or []
        gold = golds[0] if golds else ""
        retrieved = s.get("retrieved_triples") or []
        f1 = s["_f1"]
        label = _classify_label(retrieved, gold, pred, f1)
        label_counts[label] += 1
        taxonomy_rows.append({
            "id": s.get("id", ""),
            "question": s.get("question", ""),
            "gold": gold,
            "pred": pred,
            "label": label,
            "retrieved_k": len(retrieved),
        })

    (artifacts_dir / "baseline_error_taxonomy.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in taxonomy_rows), encoding="utf-8"
    )

    n = len(samples)
    taxonomy_summary = {
        "counts": dict(label_counts),
        "ratios": {k: round(v / n, 4) for k, v in label_counts.items()},
    }
    (artifacts_dir / "baseline_error_taxonomy_summary.json").write_text(
        json.dumps(taxonomy_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Step 4: Case study
    sorted_by_f1 = sorted(samples, key=lambda x: x["_f1"])
    bottom10 = sorted_by_f1[:10]
    f1_positive = [s for s in samples if s["_f1"] > 0]
    top10_raw = sorted(f1_positive, key=lambda x: x["_f1"], reverse=True)[:10]
    top10 = top10_raw
    top10_note = ""
    if len(top10) < 10:
        top10_note = f"（实际非零F1样本仅 {len(top10)} 条，不足10条）"

    def _to_case(o):
        return {
            "id": o.get("id", ""),
            "question": o.get("question", ""),
            "gold": (o.get("gold_answers") or [""])[0],
            "pred": (o.get("prediction") or "").strip(),
            "f1": o["_f1"],
            "retrieved_triples": o.get("retrieved_triples", []),
        }

    (artifacts_dir / "case_study_bottom10.json").write_text(
        json.dumps([_to_case(x) for x in bottom10], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    top10_data = {"samples": [_to_case(x) for x in top10], "n_actual": len(top10), "note": top10_note or None}
    (artifacts_dir / "case_study_top10.json").write_text(
        json.dumps(top10_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # id_integrity_report
    ids = [s.get("id", "") for s in samples]
    unique_ids = set(ids)
    id_report = {
        "n": len(samples),
        "n_unique_ids": len(unique_ids),
        "has_duplicates": len(unique_ids) != len(samples),
        "duplicate_ids": [i for i in unique_ids if ids.count(i) > 1],
    }
    (artifacts_dir / "id_integrity_report.json").write_text(
        json.dumps(id_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Step 5: Answer quality gates
    norm_preds: list[str] = []
    for s in samples:
        raw = (s.get("prediction") or "").strip()
        norm = normalize_answer(raw)
        norm_preds.append(norm)
    total_n = len(norm_preds)

    def _rate(cond) -> float:
        cnt = sum(1 for p in norm_preds if cond(p))
        return cnt / total_n if total_n else 0.0

    import re

    unknown_rate = _rate(lambda p: p.lower() == "unknown")
    very_short_rate = _rate(lambda p: len(mixed_segmentation(p)) <= 1)
    numeric_only_rate = _rate(lambda p: bool(p) and re.fullmatch(r"[0-9\\W_]+", p) is not None)
    pred_counter = Counter(norm_preds)
    most_common_count = pred_counter.most_common(1)[0][1] if pred_counter else 0
    duplicated_answer_rate = most_common_count / total_n if total_n else 0.0

    quality_gates = {
        "unknown_rate": unknown_rate,
        "very_short_rate": very_short_rate,
        "numeric_only_rate": numeric_only_rate,
        "duplicated_answer_rate": duplicated_answer_rate,
    }
    (artifacts_dir / "answer_quality_gates.json").write_text(
        json.dumps(quality_gates, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Step 6: Console report
    print("=== Audit 写入确认 ===")
    print(f"  eval.py sha256: {eval_sha[:16]}...")

    print("\n=== baseline_len_hit_summary 核心数值 ===")
    print(f"  n={len_hit['n']}")
    print(f"  pred_len_char: median={len_hit['pred_len_char']['median']:.1f}, p90={len_hit['pred_len_char']['p90']:.1f}")
    print(f"  gold_len_char: median={len_hit['gold_len_char']['median']:.1f}")
    print(f"  gold_token_hit_rate: median={len_hit['gold_token_hit_rate']['median']:.4f}")
    print(f"  f1: mean={len_hit['f1']['mean']:.4f}, median={len_hit['f1']['median']:.4f}, p90={len_hit['f1']['p90']:.4f}")

    print("\n=== taxonomy counts/ratios ===")
    for k in ["retriever_miss", "format_mismatch", "ungrounded_or_wrong", "partial_correct"]:
        c = taxonomy_summary["counts"].get(k, 0)
        r = taxonomy_summary["ratios"].get(k, 0)
        print(f"  {k}: count={c}, ratio={r}")

    print("\n=== bottom10 (F1 最低) id + f1 ===")
    for x in bottom10:
        print(f"  {x.get('id','')}: f1={x['_f1']:.4f}")

    print("\n=== top10 (F1 最高，仅 f1>0) id + f1 ===")
    if top10_note:
        print(f"  {top10_note}")
    for x in top10:
        print(f"  {x.get('id','')}: f1={x['_f1']:.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
