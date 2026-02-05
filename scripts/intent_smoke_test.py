#!/usr/bin/env python3
"""Smoke test for IntentEngine taxonomy/rules.

- 加载 configs/intent_taxonomy.yaml 与 configs/intent_rules.yaml
- 对 taxonomy 中的 examples 逐条运行 IntentEngine
- 统计：
  - 每个标签的 examples 命中率（top1 是否为该标签）
  - 是否出现高分冲突或明显歧义

该脚本仅用于快速自测，不写 runs/ 工件。
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

from framework.utils import ROOT  # type: ignore

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.intent.intent_engine import IntentEngine  # type: ignore


def main() -> int:
    engine = IntentEngine()

    import yaml

    taxo_path = ROOT / "configs" / "intent_taxonomy.yaml"
    taxo = yaml.safe_load(taxo_path.read_text(encoding="utf-8")) or {}
    labels = taxo.get("intent_labels", [])

    stats = defaultdict(lambda: Counter({"n": 0, "top1_hit": 0, "ambiguous": 0, "multi": 0}))

    for item in labels:
        name = item.get("name")
        examples = item.get("examples") or []
        for ex in examples:
            stats[name]["n"] += 1
            out = engine.predict(str(ex))
            intents = out.get("intents") or []
            top1_label = intents[0]["label"] if intents else None
            if top1_label == name:
                stats[name]["top1_hit"] += 1
            if out.get("is_ambiguous"):
                stats[name]["ambiguous"] += 1
            if out.get("is_multi_intent"):
                stats[name]["multi"] += 1

    print("== IntentEngine taxonomy examples smoke test ==")
    for name, cnt in stats.items():
        n = cnt["n"]
        if n == 0:
            continue
        hit = cnt["top1_hit"]
        amb = cnt["ambiguous"]
        multi = cnt["multi"]
        print(
            f"- {name}: n={n}, top1_hit={hit} ({hit/n:.2%}), "
            f"ambiguous={amb} ({amb/n:.2%}), multi={multi} ({multi/n:.2%})"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

