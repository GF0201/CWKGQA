#!/usr/bin/env python3
"""Build a small intent gold seed set from P0 runs.

功能（P1‑1）：
- 从若干个 `intent_workspace/runs/*/per_sample_intent_results.jsonl` 中抽样；
- 重点覆盖三类样本：
  1) top1-top2 分数差（margin）最小的高歧义样本；
  2) 命中 conflict_matrix 的样本（如 FACTOID vs COMPARISON 等）；
  3) 显式多意图样本（is_multi_intent == true）；
- 去重逻辑以样本 id 为主键；
- 输出可人工标注的模板：
  `intent_workspace/artifacts/intent_gold_seed.jsonl`
  每行字段：
    - id
    - question
    - pred_intents
    - scores: {label: score}
    - rules_triggered
    - suggested_label  (默认填写 top1 label，可人工修改)
    - notes            (默认空字符串)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

# 确保可以导入顶层模块
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from intent_workspace.src.utils import ROOT, load_yaml  # type: ignore


def _load_per_sample_intent(run_id: str) -> List[Dict[str, Any]]:
    """加载 intent_workspace/runs/<run_id>/per_sample_intent_results.jsonl。"""

    run_dir = ROOT / "intent_workspace" / "runs" / run_id
    path = run_dir / "per_sample_intent_results.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"per_sample_intent_results.jsonl not found: {path}")
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _load_conflict_pairs() -> List[Tuple[str, str]]:
    """从 configs/intent_rules.yaml 读取 conflict_matrix。"""

    cfg_path = ROOT / "configs" / "intent_rules.yaml"
    cfg = load_yaml(cfg_path)
    pairs = cfg.get("conflict_matrix") or []
    out: List[Tuple[str, str]] = []
    for item in pairs:
        if not isinstance(item, Sequence) or len(item) != 2:
            continue
        a, b = str(item[0]), str(item[1])
        out.append((a, b))
    return out


def _has_conflict(labels: Sequence[str], conflict_pairs: List[Tuple[str, str]]) -> bool:
    """判断当前样本的标签集合是否命中 conflict_matrix 任一 pair。"""

    label_set = set(labels)
    for a, b in conflict_pairs:
        if a in label_set and b in label_set:
            return True
    return False


def _top2_margin(pred_intents: Sequence[Dict[str, Any]]) -> float:
    """计算 top1-top2 margin；若不足 2 个标签则返回 1.0。"""

    if not pred_intents:
        return 1.0
    scores = sorted(
        [float(it.get("score", 0.0)) for it in pred_intents],
        reverse=True,
    )
    if len(scores) == 1:
        return 1.0
    return scores[0] - scores[1]


def _collect_candidates(
    runs: Sequence[str],
    conflict_pairs: List[Tuple[str, str]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """从多个 run 中收集三类候选样本：高歧义 / 冲突矩阵命中 / 多意图。"""

    ambiguous_candidates: List[Dict[str, Any]] = []
    conflict_candidates: List[Dict[str, Any]] = []
    multi_candidates: List[Dict[str, Any]] = []

    for run_id in runs:
        rows = _load_per_sample_intent(run_id)
        for r in rows:
            pred_intents = r.get("pred_intents") or []
            labels = [str(it.get("label")) for it in pred_intents if it.get("label") is not None]

            margin = _top2_margin(pred_intents)
            r_with_meta = dict(r)
            r_with_meta["_margin"] = margin
            r_with_meta["_source_run_id"] = run_id

            # 高歧义候选：margin 小 或 标记为 is_ambiguous
            if r.get("is_ambiguous") or margin <= 0.15:
                ambiguous_candidates.append(r_with_meta)

            # 冲突矩阵命中：标签对出现在 conflict_matrix
            if labels and _has_conflict(labels, conflict_pairs):
                conflict_candidates.append(r_with_meta)

            # 多意图候选
            if r.get("is_multi_intent"):
                multi_candidates.append(r_with_meta)

    # 按 margin 升序排序高歧义样本（更靠前 → 更歧义）
    ambiguous_candidates.sort(key=lambda x: float(x.get("_margin", 1.0)))
    return ambiguous_candidates, conflict_candidates, multi_candidates


def _build_seed(
    ambiguous: List[Dict[str, Any]],
    conflict: List[Dict[str, Any]],
    multi: List[Dict[str, Any]],
    *,
    n_ambiguous: int,
    n_conflict: int,
    n_multi: int,
) -> List[Dict[str, Any]]:
    """按类别抽样并去重，构造最终 gold seed 列表。"""

    seed_rows: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    def _take_from(cands: List[Dict[str, Any]], k: int) -> None:
        for r in cands:
            sid = str(r.get("id"))
            if not sid or sid in seen_ids:
                continue
            seed_rows.append(r)
            seen_ids.add(sid)
            if len([x for x in seed_rows if x is r or True]) >= len(seed_rows) and len(seen_ids) >= 0:
                # continue; the real limit is handled outside by caller per category
                pass

    # 逐类抽样，先歧义、再冲突、最后多意图；去重以 id 为键
    count = 0
    for r in ambiguous:
        if count >= n_ambiguous:
            break
        sid = str(r.get("id"))
        if not sid or sid in seen_ids:
            continue
        seed_rows.append(r)
        seen_ids.add(sid)
        count += 1

    count_conf = 0
    for r in conflict:
        if count_conf >= n_conflict:
            break
        sid = str(r.get("id"))
        if not sid or sid in seen_ids:
            continue
        seed_rows.append(r)
        seen_ids.add(sid)
        count_conf += 1

    count_multi = 0
    for r in multi:
        if count_multi >= n_multi:
            break
        sid = str(r.get("id"))
        if not sid or sid in seen_ids:
            continue
        seed_rows.append(r)
        seen_ids.add(sid)
        count_multi += 1

    return seed_rows


def _to_gold_record(row: Dict[str, Any]) -> Dict[str, Any]:
    """将 per-sample 行转换为 gold_seed 模板行。"""

    sid = row.get("id")
    q = row.get("question")
    pred_intents = row.get("pred_intents") or []
    rules_triggered = row.get("rules_fired") or []

    scores = {str(it.get("label")): float(it.get("score", 0.0)) for it in pred_intents}
    suggested_label = pred_intents[0].get("label") if pred_intents else None

    return {
        "id": sid,
        "question": q,
        "pred_intents": pred_intents,
        "scores": scores,
        "rules_triggered": rules_triggered,
        "suggested_label": suggested_label,
        "notes": "",
        "source_run_id": row.get("_source_run_id"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build intent gold seed set from P0 runs.")
    parser.add_argument(
        "--runs",
        nargs="+",
        required=True,
        help=(
            "Intent workspace run ids under intent_workspace/runs/ to use as candidates "
            "(e.g. intent_2026..._rule_v1 intent_2026..._route ...)."
        ),
    )
    parser.add_argument(
        "--n_ambiguous",
        type=int,
        default=30,
        help="Target number of high-ambiguity samples.",
    )
    parser.add_argument(
        "--n_conflict",
        type=int,
        default=30,
        help="Target number of conflict-matrix samples.",
    )
    parser.add_argument(
        "--n_multi",
        type=int,
        default=30,
        help="Target number of multi-intent samples.",
    )
    args = parser.parse_args()

    conflict_pairs = _load_conflict_pairs()
    ambiguous_candidates, conflict_candidates, multi_candidates = _collect_candidates(
        args.runs, conflict_pairs
    )

    seed_rows_raw = _build_seed(
        ambiguous_candidates,
        conflict_candidates,
        multi_candidates,
        n_ambiguous=args.n_ambiguous,
        n_conflict=args.n_conflict,
        n_multi=args.n_multi,
    )

    gold_records = [_to_gold_record(r) for r in seed_rows_raw]

    artifacts_dir = ROOT / "intent_workspace" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifacts_dir / "intent_gold_seed.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for rec in gold_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(
        f"Wrote {out_path} with {len(gold_records)} rows "
        f"(ambiguous_candidates={len(ambiguous_candidates)}, "
        f"conflict_candidates={len(conflict_candidates)}, "
        f"multi_candidates={len(multi_candidates)})"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

