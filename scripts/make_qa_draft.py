#!/usr/bin/env python3
"""Quickly build a draft QA evaluation set from the unified KG."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Callable, Iterable, List, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Optional import from framework.utils if the project provides it.
_load_jsonl: Callable[[Path], Sequence[dict]] | None = None

try:  # pragma: no cover - optional dependency
    from framework.utils.io import load_jsonl as _fw_load_jsonl  # type: ignore

    _load_jsonl = _fw_load_jsonl
except Exception:  # pragma: no cover - fallback to core utilities
    pass

if _load_jsonl is None:
    from core import load_jsonl as _core_load_jsonl  # type: ignore

    _load_jsonl = _core_load_jsonl


DEFAULT_TRIPLES = ROOT / "datasets" / "domain_main_kg" / "processed" / "merged" / "triples.jsonl"
DEFAULT_OUTPUT = ROOT / "datasets" / "domain_main_qa" / "draft_pool_200.jsonl"
DEFAULT_SAMPLE_N = 200
DEFAULT_SEED = 42

# 过于通用的 predicate，采样时优先跳过或降低优先级
GENERIC_PREDICATES = frozenset({"是", "有", "包含"})


def _normalize_text(text: str | None) -> str:
    return (text or "").strip()


def _build_question(subject: str, predicate: str) -> str:
    if not subject and not predicate:
        return "请给出答案？"
    if not predicate:
        return f"{subject} 是什么？"
    return f"{subject} 的 {predicate} 是什么？"


def _is_generic_predicate(pred: str) -> bool:
    return pred.strip() in GENERIC_PREDICATES


def _choose_indices(
    triples: Sequence[dict],
    sample_n: int,
    seed: int,
) -> List[int]:
    """优先采样 predicate 非通用的三元组；不足时用通用 predicate 补足。"""
    if not triples:
        return []
    rng = random.Random(seed)
    preferred: List[int] = []
    fallback: List[int] = []
    for i, t in enumerate(triples):
        pred = _normalize_text(t.get("predicate") or t.get("connect"))
        if _is_generic_predicate(pred):
            fallback.append(i)
        else:
            preferred.append(i)
    rng.shuffle(preferred)
    rng.shuffle(fallback)
    k = min(sample_n, len(triples))
    chosen = preferred[:k]
    if len(chosen) < k:
        chosen.extend(fallback[: k - len(chosen)])
    return chosen


def _make_entry(idx: int, triple: dict) -> dict:
    subj = _normalize_text(triple.get("subject") or triple.get("head"))
    pred = _normalize_text(triple.get("predicate") or triple.get("connect"))
    obj = _normalize_text(triple.get("object") or triple.get("tail"))
    question = _build_question(subj, pred)
    evidence = [subj, pred, obj]
    return {
        "id": f"draft_{idx}",
        "question": question,
        "gold_answers": [obj] if obj else [],
        "evidence_triple": evidence,
    }


def generate_draft(
    triples: Sequence[dict],
    sample_n: int,
    seed: int,
) -> Iterable[dict]:
    indices = _choose_indices(triples, sample_n, seed)
    for i, triple_idx in enumerate(indices):
        yield _make_entry(i, triples[triple_idx])


def main() -> int:
    parser = argparse.ArgumentParser(description="Make QA draft set from KG triples")
    parser.add_argument("--triples", type=Path, default=DEFAULT_TRIPLES, help="Path to triples.jsonl")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="Output draft JSONL path")
    parser.add_argument("--sample-n", type=int, default=DEFAULT_SAMPLE_N, help="Number of triples to sample")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed")
    args = parser.parse_args()

    triples_path: Path = args.triples
    if not triples_path.exists():
        print(f"[make_qa_draft] Missing triples file: {triples_path}", file=sys.stderr)
        return 1

    triples = list(_load_jsonl(triples_path))  # type: ignore[arg-type]
    if not triples:
        print(f"[make_qa_draft] No triples loaded from {triples_path}", file=sys.stderr)
        return 1

    draft_entries = list(generate_draft(triples, args.sample_n, args.seed))
    out_path: Path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in draft_entries:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"[make_qa_draft] Draft saved to {out_path} (samples={len(draft_entries)})")
    print("[make_qa_draft] 已生成 {n} 条候选 QA。请打开文件，挑选出质量最好的 50 条，润色后另存为 `datasets/domain_main_qa/test.jsonl`。".format(n=len(draft_entries)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
