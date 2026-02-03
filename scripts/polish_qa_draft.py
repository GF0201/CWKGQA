#!/usr/bin/env python3
"""Auto-polish QA draft: filter garbage, polish questions, output test.jsonl.

遵循 Prompt 规则：筛选、润色、保留格式。gold_answers 与 evidence_triple 不得修改。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import load_jsonl  # type: ignore

DRAFT = ROOT / "datasets" / "domain_main_qa" / "draft_pool_200.jsonl"
OUT = ROOT / "datasets" / "domain_main_qa" / "test.jsonl"
KEEP_N = 55  # 保留 50-60 条


def _should_drop(entry: dict) -> bool:
    """筛选：丢弃无意义、重复、无法改写的数据。"""
    ga = entry.get("gold_answers") or []
    if not ga or not str(ga[0]).strip():
        return True
    ev = entry.get("evidence_triple") or []
    if len(ev) < 3:
        return True
    subj, pred, obj = (str(ev[0]).strip(), str(ev[1]).strip(), str(ev[2]).strip())
    # 过于空泛的答案
    if len(obj) < 3:
        return True
    # 元信息（章节、讨论位置等）
    meta = ("讨论将在", "将在", "第.*章", "本章", "先介绍")
    if any(re.search(m, pred) for m in meta):
        return True
    # 答案与问题几乎相同（重复）
    if "是" in pred and obj.startswith("是") and subj in obj:
        return True
    # 太琐碎
    if obj in ("同义词", "很多因素引起的") or pred in ("讨论", "流行"):
        return True
    return False


def _polish_question(entry: dict) -> str:
    """润色：将机械语言改为自然问句。不修改 gold_answers / evidence_triple。"""
    ev = entry.get("evidence_triple") or []
    if len(ev) < 3:
        return entry.get("question", "请给出答案？")
    subj, pred, obj = ev[0], ev[1], ev[2]
    subj = (subj or "").strip()
    pred = (pred or "").strip()

    if not pred:
        return f"{subj} 是什么？" if subj else "请给出答案？"

    # 常见谓词 → 自然问法
    polish_map = {
        "是": f"{subj} 最核心的特性或定义是什么？",
        "有": f"{subj} 具有哪些特点？",
        "包含": f"{subj} 包含哪些内容？",
        "允许": f"{subj} 允许完成什么功能？",
        "提供": f"{subj} 提供哪些功能或服务？",
        "包括": f"{subj} 包括哪些方面或内容？",
        "用于": f"{subj} 主要用于什么？",
        "使用": f"{subj} 使用什么技术或方法？",
        "采用": f"{subj} 采用什么技术或方案？",
        "指": f"{subj} 的具体含义是什么？",
        "定义为": f"{subj} 的定义是什么？",
        "规定": f"{subj} 有哪些规定或要求？",
        "表示": f"{subj} 表示什么？",
        "支持": f"{subj} 支持什么功能？",
        "适用于": f"{subj} 适用于哪些场景？",
        "产生于": f"{subj} 产生于什么原因？",
        "要求": f"{subj} 有哪些要求？",
        "需要": f"{subj} 需要满足什么条件？",
        "通过": f"{subj} 通过什么方式实现？",
        "将": f"{subj} 如何划分或处理？",
        "由": f"{subj} 由什么组成？",
        "称为": f"{subj} 又称为或称为什么？",
        "对应": f"{subj} 对应什么概念？",
        "进行": f"{subj} 进行什么操作或转换？",
        "负责管理": f"{subj} 负责管理哪些内容？",
        "详细地指明了": f"{subj} 详细指明了哪些参数或信息？",
        "总共不超过": f"{subj} 的长度或数量限制是多少？",
        "广泛地使用": f"{subj} 广泛使用什么技术？",
        "存放": f"{subj} 中存放什么信息？",
        "更换": f"{subj} 更换时需要切换什么？",
    }
    if pred in polish_map:
        return polish_map[pred]

    # 谓词含"可以/能"等
    if "可以" in pred or "能" in pred:
        return f"{subj} {pred}什么？"
    if "在" in pred and len(pred) <= 8:
        return f"{subj} {pred}时会发生什么？"
    # 通用
    if len(pred) <= 6:
        return f"{subj} 在 {pred} 方面有什么特点？"
    return f"{subj} {pred}的具体内容是什么？"


def main() -> int:
    if not DRAFT.exists():
        print(f"[polish_qa_draft] Missing: {DRAFT}", file=sys.stderr)
        return 1

    entries = list(load_jsonl(DRAFT))
    if not entries:
        print("[polish_qa_draft] No entries loaded.", file=sys.stderr)
        return 1

    kept: list[dict] = []
    for e in entries:
        if _should_drop(e):
            continue
        out = {
            "id": e.get("id", ""),
            "question": _polish_question(e),
            "gold_answers": e.get("gold_answers", []),
            "evidence_triple": e.get("evidence_triple", []),
        }
        kept.append(out)

    # 截断为 KEEP_N 条
    final = kept[:KEEP_N]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for row in final:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"[polish_qa_draft] Polished {len(kept)} entries, kept top {len(final)} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
