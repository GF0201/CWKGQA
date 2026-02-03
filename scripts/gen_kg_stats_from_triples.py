#!/usr/bin/env python3
"""Generate kg_stats.csv from triples (JSONL or TSV).

Output columns: metric, value
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_triples(path: Path) -> list[dict]:
    triples: list[dict] = []
    if path.suffix.lower() == ".tsv":
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for i, row in enumerate(reader):
                s = (row.get("subject") or row.get("head") or "").strip()
                p = (row.get("predicate") or row.get("connect") or "").strip()
                o = (row.get("object") or row.get("tail") or "").strip()
                triples.append({"subject": s, "predicate": p, "object": o})
    else:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                s = (obj.get("subject") or obj.get("head") or "").strip()
                p = (obj.get("predicate") or obj.get("connect") or "").strip()
                o = (obj.get("object") or obj.get("tail") or "").strip()
                triples.append({"subject": s, "predicate": p, "object": o})
    return triples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="triples.jsonl or triples.tsv")
    parser.add_argument("--out", type=str, required=True, help="Output kg_stats.csv")
    args = parser.parse_args()

    inp = Path(args.input)
    out_path = Path(args.out)
    if not inp.exists():
        print(f"Input not found: {inp}", file=sys.stderr)
        return 1

    triples = _load_triples(inp)
    if not triples:
        print("No triples loaded", file=sys.stderr)
        return 1

    subjects = [t["subject"] for t in triples]
    predicates = [t["predicate"] for t in triples]
    objects = [t["object"] for t in triples]
    entities = set(subjects) | set(objects)

    pred_counter = Counter(predicates)
    subj_counter = Counter(subjects)
    obj_counter = Counter(objects)

    rows: list[tuple[str, str]] = [
        ("n_triples", str(len(triples))),
        ("n_entities", str(len(entities))),
        ("n_subjects_unique", str(len(set(subjects)))),
        ("n_objects_unique", str(len(set(objects)))),
        ("n_predicates_unique", str(len(set(predicates)))),
    ]
    for k, v in pred_counter.most_common(15):
        rows.append((f"pred_count_{k[:50]}", str(v)))
    for k, v in subj_counter.most_common(10):
        rows.append((f"head_count_{k[:50]}", str(v)))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        for r in rows:
            w.writerow(r)
    print(f"Wrote {out_path} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
