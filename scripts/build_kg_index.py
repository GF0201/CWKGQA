#!/usr/bin/env python3
"""Build KG adjacency indices: forward, backward, hp_to_t.

- forward: head -> [(predicate, tail), ...]
- backward: tail -> [(head, predicate), ...]
- hp_to_t: (head, predicate) -> [tail, ...]

Output: index/forward.json, backward.json, hp_to_t.json (or .jsonl for large)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_triples(path: Path) -> list[dict]:
    import csv

    triples: list[dict] = []
    if path.suffix.lower() == ".tsv":
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
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
    parser.add_argument("--out_dir", type=str, required=True, help="Output index dir")
    args = parser.parse_args()

    inp = Path(args.input)
    out_dir = Path(args.out_dir)
    if not inp.exists():
        print(f"Input not found: {inp}", file=sys.stderr)
        return 1

    triples = _load_triples(inp)
    if not triples:
        print("No triples loaded", file=sys.stderr)
        return 1

    forward: dict[str, list[tuple[str, str]]] = defaultdict(list)
    backward: dict[str, list[tuple[str, str]]] = defaultdict(list)
    hp_to_t: dict[tuple[str, str], list[str]] = defaultdict(list)

    for t in triples:
        h, p, o = t["subject"], t["predicate"], t["object"]
        if not h and not p and not o:
            continue
        forward[h].append((p, o))
        backward[o].append((h, p))
        hp_to_t[(h, p)].append(o)

    # Convert to JSON-serializable (tuple keys -> str keys for hp_to_t)
    hp_to_t_serial = {f"{h}\t{p}": v for (h, p), v in hp_to_t.items()}
    forward_serial = {k: v for k, v in forward.items()}
    backward_serial = {k: v for k, v in backward.items()}

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in [
        ("forward.json", forward_serial),
        ("backward.json", backward_serial),
        ("hp_to_t.json", hp_to_t_serial),
    ]:
        p = out_dir / name
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=0)
        print(f"Wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
