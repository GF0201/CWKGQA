#!/usr/bin/env python3
"""Generate casebook and intent-based slices for P2.

输出：
- intent_workspace/artifacts/casebook.md
    - 若干典型样例（高歧义、多意图、route 生效、澄清生效、失败/边界）。
- intent_workspace/artifacts/error_slices.md
    - 按 top1 intent label 聚合的简单切片统计（样本数、EM/F1/UNKNOWN 比例）。
- intent_workspace/artifacts/rules_trigger_frequency.csv
    - 规则触发频次统计，用于审查高频/低频规则。

依赖：
- P0 已完成的 4 个主线 run：
    - exp_default_intent_none_real_v1
    - exp_default_intent_rule_v1_real_v1
    - exp_default_intent_route_real_v1
    - exp_default_intent_clarify_real_v1
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 确保可以导入顶层模块
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.utils import ROOT, RUNS_DIR, load_jsonl  # type: ignore


def _load_per_sample_main(run_id: str) -> List[Dict[str, Any]]:
    run_dir = RUNS_DIR / run_id
    path = run_dir / "artifacts" / "per_sample_results.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"per_sample_results.jsonl not found: {path}")
    return load_jsonl(path)


def _index_by_id(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        sid = str(r.get("id"))
        if not sid:
            continue
        out[sid] = r
    return out


def _collect_clarify_cases(
    base_rule: Dict[str, Dict[str, Any]],
    clarify: Dict[str, Dict[str, Any]],
    k: int = 3,
) -> List[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    """clarify 生效样例：clarify_run 将答案强制为 UNKNOWN。"""

    cases: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = []
    for sid, row_c in clarify.items():
        if not row_c.get("clarify_applied"):
            continue
        row_b = base_rule.get(sid)
        if not row_b:
            continue
        cases.append((sid, row_b, row_c))
    # 按 EM 降序排序 base_rule 的表现，优先挑选高价值样本
    cases.sort(key=lambda t: float(t[1].get("f1", 0.0)), reverse=True)
    return cases[:k]


def _collect_multi_intent_cases(
    base_rule: Dict[str, Dict[str, Any]],
    k: int = 3,
) -> List[Tuple[str, Dict[str, Any]]]:
    """多意图样例：is_multi_intent == True。"""

    cases: List[Tuple[str, Dict[str, Any]]] = []
    for sid, row in base_rule.items():
        ip = row.get("intent_pred") or {}
        if ip.get("is_multi_intent"):
            cases.append((sid, row))
    # 优先挑选 F1 较低的样本，便于展示困难案例
    cases.sort(key=lambda t: float(t[1].get("f1", 1.0)))
    return cases[:k]


def _collect_route_active_cases(
    base_rule: Dict[str, Dict[str, Any]],
    route: Dict[str, Dict[str, Any]],
    k: int = 2,
) -> List[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    """route 生效样例：retrieved_triples 数量或 final_answer 发生变化。"""

    cases: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = []
    for sid, row_b in base_rule.items():
        row_r = route.get(sid)
        if not row_r:
            continue
        triples_b = row_b.get("retrieved_triples") or []
        triples_r = row_r.get("retrieved_triples") or []
        ans_b = row_b.get("final_answer")
        ans_r = row_r.get("final_answer")
        changed_retrieval = len(triples_r) != len(triples_b)
        changed_answer = ans_r != ans_b
        if changed_retrieval or changed_answer:
            cases.append((sid, row_b, row_r))
    # 优先选择同时改变检索和答案的样本
    def _key(t):
        _, rb, rr = t
        changed_ans = rb.get("final_answer") != rr.get("final_answer")
        changed_ctx = len(rb.get("retrieved_triples") or []) != len(
            rr.get("retrieved_triples") or []
        )
        score = 0
        if changed_ans:
            score += 2
        if changed_ctx:
            score += 1
        return -score

    cases.sort(key=_key)
    return cases[:k]


def _collect_failure_cases(
    rule_v1: Dict[str, Dict[str, Any]],
    clarify: Dict[str, Dict[str, Any]],
    k: int = 2,
) -> List[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    """失败/边界案例：F1 很低、UNKNOWN 较多等。"""

    cases: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = []
    for sid, row_r in rule_v1.items():
        row_c = clarify.get(sid)
        if not row_c:
            continue
        f1_r = float(row_r.get("f1", 1.0))
        f1_c = float(row_c.get("f1", 1.0))
        if f1_r < 0.2 or f1_c < 0.2:
            cases.append((sid, row_r, row_c))
    # 按 F1 升序排序
    cases.sort(key=lambda t: float(min(t[1].get("f1", 1.0), t[2].get("f1", 1.0))))
    return cases[:k]


def _format_intent_pred(ip: Dict[str, Any]) -> str:
    intents = ip.get("intents") or []
    parts = []
    for it in intents:
        parts.append(f"{it.get('label')}({it.get('score'):.2f})")
    return ", ".join(parts) if parts else "(no intents)"


def _build_casebook(
    run_none_id: str,
    run_rule_id: str,
    run_route_id: str,
    run_clarify_id: str,
) -> str:
    """生成 casebook.md 的内容。"""

    rows_none = _index_by_id(_load_per_sample_main(run_none_id))
    rows_rule = _index_by_id(_load_per_sample_main(run_rule_id))
    rows_route = _index_by_id(_load_per_sample_main(run_route_id))
    rows_clarify = _index_by_id(_load_per_sample_main(run_clarify_id))

    clarify_cases = _collect_clarify_cases(rows_rule, rows_clarify, k=3)
    multi_cases = _collect_multi_intent_cases(rows_rule, k=3)
    route_cases = _collect_route_active_cases(rows_rule, rows_route, k=2)
    failure_cases = _collect_failure_cases(rows_rule, rows_clarify, k=2)

    lines: List[str] = []
    lines.append("# Intent casebook (from mainline runs)")
    lines.append("")
    lines.append(f"- Source runs (none / rule / route / clarify):")
    lines.append(
        f"  - `{run_none_id}`, `{run_rule_id}`, `{run_route_id}`, `{run_clarify_id}`"
    )
    lines.append("")

    case_idx = 1

    def _add_case_header(title: str) -> None:
        lines.append("")
        lines.append(f"## {title}")
        lines.append("")

    # 1) clarify 生效案例
    _add_case_header("Clarify-applied cases (歧义 + 强制 UNKNOWN)")
    for sid, row_b, row_c in clarify_cases:
        ip = row_c.get("intent_pred") or {}
        lines.append(f"### Case {case_idx}: id={sid}")
        case_idx += 1
        lines.append(f"- Question: {row_c.get('question')}")
        lines.append(f"- Intent prediction: {_format_intent_pred(ip)}")
        lines.append(
            f"- Clarification question: {ip.get('clarification_question') or '(none)'}"
        )
        lines.append(
            f"- Clarification options: {', '.join(ip.get('clarification_options') or []) or '(none)'}"
        )
        lines.append(
            f"- Before clarify (rule_v1 final_answer): {row_b.get('final_answer')!r}"
        )
        lines.append(
            f"- After clarify (clarify final_answer): {row_c.get('final_answer')!r}"
        )
        lines.append(
            f"- EM/F1 before → after: {row_b.get('em')} / {row_b.get('f1'):.3f} "
            f"→ {row_c.get('em')} / {row_c.get('f1'):.3f}"
        )
        rules = []
        for it in ip.get("intents") or []:
            for ev in it.get("evidence_rules_triggered") or []:
                rules.append(ev.get("rule_id"))
        lines.append(
            f"- Triggered rules: {', '.join(sorted(set(rules))) or '(none)'}"
        )
        lines.append("")

    # 2) 多意图案例
    _add_case_header("Multi-intent cases")
    for sid, row in multi_cases:
        ip = row.get("intent_pred") or {}
        lines.append(f"### Case {case_idx}: id={sid}")
        case_idx += 1
        lines.append(f"- Question: {row.get('question')}")
        lines.append(f"- Intent prediction: {_format_intent_pred(ip)}")
        lines.append(f"- is_multi_intent: {ip.get('is_multi_intent')}")
        lines.append(f"- is_ambiguous: {ip.get('is_ambiguous')}")
        lines.append(f"- Final answer (rule_v1): {row.get('final_answer')!r}")
        lines.append(f"- EM/F1: {row.get('em')} / {row.get('f1'):.3f}")
        lines.append("")

    # 3) route 生效案例
    _add_case_header("Route-active cases (retrieval/answer changed)")
    for sid, row_b, row_r in route_cases:
        ip = row_r.get("intent_pred") or {}
        triples_b = row_b.get("retrieved_triples") or []
        triples_r = row_r.get("retrieved_triples") or []
        lines.append(f"### Case {case_idx}: id={sid}")
        case_idx += 1
        lines.append(f"- Question: {row_r.get('question')}")
        lines.append(f"- Intent prediction (route): {_format_intent_pred(ip)}")
        lines.append(f"- Retrieved triples: rule_v1={len(triples_b)}, route={len(triples_r)}")
        lines.append(
            f"- Final answer: rule_v1={row_b.get('final_answer')!r}, "
            f"route={row_r.get('final_answer')!r}"
        )
        lines.append(
            f"- EM/F1: rule_v1={row_b.get('em')}/{row_b.get('f1'):.3f}, "
            f"route={row_r.get('em')}/{row_r.get('f1'):.3f}"
        )
        lines.append("")

    # 4) 失败/边界案例
    _add_case_header("Failure/boundary cases")
    for sid, row_r, row_c in failure_cases:
        lines.append(f"### Case {case_idx}: id={sid}")
        case_idx += 1
        lines.append(f"- Question: {row_r.get('question')}")
        lines.append(
            f"- Final answer (rule_v1 / clarify): {row_r.get('final_answer')!r} / "
            f"{row_c.get('final_answer')!r}"
        )
        lines.append(
            f"- EM/F1 (rule_v1 / clarify): {row_r.get('em')}/{row_r.get('f1'):.3f} / "
            f"{row_c.get('em')}/{row_c.get('f1'):.3f}"
        )
        lines.append("")

    return "\n".join(lines)


def _build_error_slices(
    run_rule_id: str,
) -> str:
    """按 top1 intent label 统计 EM/F1/UNKNOWN 比例。"""

    rows = _load_per_sample_main(run_rule_id)
    buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "em_sum": 0.0, "f1_sum": 0.0, "n_unknown": 0}
    )

    for r in rows:
        ip = r.get("intent_pred") or {}
        intents = ip.get("intents") or []
        if intents:
            top_label = str(intents[0].get("label"))
        else:
            top_label = "NONE"
        b = buckets[top_label]
        b["n"] += 1
        b["em_sum"] += float(r.get("em", 0.0) or 0.0)
        b["f1_sum"] += float(r.get("f1", 0.0) or 0.0)
        if str(r.get("final_answer") or "") == "UNKNOWN":
            b["n_unknown"] += 1

    lines: List[str] = []
    lines.append("# Error slices by top1 intent label (rule_v1)")
    lines.append("")
    lines.append(f"- Source run: `{run_rule_id}`")
    lines.append("")
    lines.append("| intent_label | n | EM_avg | F1_avg | unknown_rate |")
    lines.append("|-------------|---|--------|--------|-------------|")
    for label, b in sorted(buckets.items(), key=lambda kv: kv[0]):
        n = b["n"]
        em_avg = b["em_sum"] / n if n else 0.0
        f1_avg = b["f1_sum"] / n if n else 0.0
        unk_rate = b["n_unknown"] / n if n else 0.0
        lines.append(
            f"| {label} | {n} | {em_avg:.3f} | {f1_avg:.3f} | {unk_rate:.3f} |"
        )

    return "\n".join(lines)


def _write_rules_trigger_frequency(run_rule_id: str, out_csv: Path) -> None:
    """统计规则触发频次。"""

    rows = _load_per_sample_main(run_rule_id)
    counter: Counter[Tuple[str, str]] = Counter()
    total = 0
    for r in rows:
        ip = r.get("intent_pred") or {}
        for it in ip.get("intents") or []:
            label = str(it.get("label"))
            for ev in it.get("evidence_rules_triggered") or []:
                rid = str(ev.get("rule_id"))
                if not rid:
                    continue
                counter[(rid, label)] += 1
                total += 1

    fieldnames = ["rule_id", "label", "count", "ratio"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=fieldnames)
        writer.writeheader()
        for (rid, label), cnt in counter.most_common():
            writer.writerow(
                {
                    "rule_id": rid,
                    "label": label,
                    "count": cnt,
                    "ratio": cnt / total if total else 0.0,
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate intent casebook and slices.")
    parser.add_argument(
        "--run_none",
        type=str,
        default="exp_default_intent_none_real_v1",
        help="Mainline run id with intent_mode=none.",
    )
    parser.add_argument(
        "--run_rule_v1",
        type=str,
        default="exp_default_intent_rule_v1_real_v1",
        help="Mainline run id with intent_mode=rule_v1.",
    )
    parser.add_argument(
        "--run_route",
        type=str,
        default="exp_default_intent_route_real_v1",
        help="Mainline run id with intent_mode=rule_v1_route.",
    )
    parser.add_argument(
        "--run_clarify",
        type=str,
        default="exp_default_intent_clarify_real_v1",
        help="Mainline run id with intent_mode=rule_v1_clarify.",
    )
    args = parser.parse_args()

    artifacts_dir = ROOT / "intent_workspace" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # casebook
    casebook_md = _build_casebook(
        args.run_none, args.run_rule_v1, args.run_route, args.run_clarify
    )
    (artifacts_dir / "casebook.md").write_text(casebook_md, encoding="utf-8")

    # error slices
    error_slices_md = _build_error_slices(args.run_rule_v1)
    (artifacts_dir / "error_slices.md").write_text(error_slices_md, encoding="utf-8")

    # rules trigger frequency
    _write_rules_trigger_frequency(
        args.run_rule_v1, artifacts_dir / "rules_trigger_frequency.csv"
    )

    print(f"Wrote {artifacts_dir / 'casebook.md'}")
    print(f"Wrote {artifacts_dir / 'error_slices.md'}")
    print(f"Wrote {artifacts_dir / 'rules_trigger_frequency.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

