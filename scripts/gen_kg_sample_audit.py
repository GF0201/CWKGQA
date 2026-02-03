#!/usr/bin/env python3
"""Generate a KG triples sampling audit sheet.

Reads an input triples file (TSV or JSONL), randomly samples N triples,
and writes:

- runs/<id>/artifacts/kg_sample_audit.csv
- runs/<id>/artifacts/kg_sample_audit_summary.json

The CSV is intended for manual labelling (strict/relaxed), while the JSON
summary can be used directly in metrics or reports.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import set_seed, DualLogger, save_json  # type: ignore


def _load_triples(path: Path, fmt: str) -> List[Dict]:
    if fmt == "tsv":
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)
    else:  # jsonl
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    triples: List[Dict] = []
    for i, row in enumerate(rows):
        triple_id = row.get("triple_id", row.get("sid", str(i)))
        subj = row.get("subject", row.get("s", row.get("head", "")))
        pred = row.get("predicate", row.get("p", row.get("connect", "")))
        obj = row.get("object", row.get("o", row.get("tail", "")))
        triples.append(
            {
                "triple_id": str(triple_id),
                "subject": str(subj),
                "predicate": str(pred),
                "object": str(obj),
            }
        )
    return triples


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate KG triples sampling audit sheet")
    parser.add_argument("--input", type=str, required=True, help="Path to triples.(tsv|jsonl)")
    parser.add_argument(
        "--format",
        type=str,
        choices=["tsv", "jsonl"],
        default=None,
        help="Input format; default inferred from extension",
    )
    parser.add_argument("--n", type=int, default=200, help="Number of triples to sample")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output-id",
        type=str,
        default=None,
        help="Custom run_id; default: kg_audit_<timestamp>",
    )
    parser.add_argument(
        "--summarize-only",
        action="store_true",
        help="Only read existing audit CSV and write summary.json without resampling",
    )
    args = parser.parse_args()

    set_seed(args.seed)
    triples_path = Path(args.input)

    exp_id = args.output_id or f"kg_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = ROOT / "runs" / exp_id
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = DualLogger(run_dir, "run.log")
    logger.log(f"argv: {' '.join(__import__('sys').argv)}")
    logger.log(f"KG sample audit run_id={exp_id}")

    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    csv_path = artifacts_dir / "kg_sample_audit.csv"
    summary_path = artifacts_dir / "kg_sample_audit_summary.json"

    if args.summarize_only:
        if not csv_path.exists():
            raise FileNotFoundError(f"{csv_path} not found; cannot summarize-only")
    else:
        if args.n <= 0:
            raise ValueError(f"n must be > 0, got {args.n}")
        if args.format is None:
            if triples_path.suffix.lower() == ".tsv":
                fmt = "tsv"
            else:
                fmt = "jsonl"
        else:
            fmt = args.format

        triples = _load_triples(triples_path, fmt)
        if not triples:
            raise ValueError(f"No triples loaded from {triples_path}")

        n_available = len(triples)
        n = min(args.n, n_available)
        logger.log(f"Loaded {n_available} triples, sampling N={n} with seed={args.seed}")

        rng = random.Random(args.seed)
        indices = list(range(n_available))
        rng.shuffle(indices)
        chosen = [triples[i] for i in indices[:n]]

        # Write CSV with empty labels/notes for manual annotation
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "triple_id",
                    "subject",
                    "predicate",
                    "object",
                    "label_strict",
                    "label_relaxed",
                    "note",
                ]
            )
            for t in chosen:
                writer.writerow(
                    [
                        t["triple_id"],
                        t["subject"],
                        t["predicate"],
                        t["object"],
                        "",
                        "",
                        "",
                    ]
                )
        logger.log(f"Wrote audit CSV with {n} rows to {csv_path}")

    # Summarise (works for both first run and summarize-only)
    total_rows = 0
    n_annotated_strict = 0
    n_correct_strict = 0
    n_annotated_relaxed = 0
    n_correct_relaxed = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            ls = (row.get("label_strict") or "").strip()
            lr = (row.get("label_relaxed") or "").strip()
            if ls:
                n_annotated_strict += 1
                if ls.lower() == "correct":
                    n_correct_strict += 1
            if lr:
                n_annotated_relaxed += 1
                if lr.lower() == "correct":
                    n_correct_relaxed += 1

    strict_precision = (
        n_correct_strict / n_annotated_strict if n_annotated_strict > 0 else None
    )
    relaxed_precision = (
        n_correct_relaxed / n_annotated_relaxed if n_annotated_relaxed > 0 else None
    )

    summary = {
        "n": total_rows,
        "n_annotated_strict": n_annotated_strict,
        "n_correct_strict": n_correct_strict,
        "strict_precision": strict_precision,
        "n_annotated_relaxed": n_annotated_relaxed,
        "n_correct_relaxed": n_correct_relaxed,
        "relaxed_precision": relaxed_precision,
        "seed": args.seed,
        "input": str(triples_path),
    }
    save_json(summary, summary_path)
    logger.log(f"Wrote summary JSON to {summary_path}")
    logger.log("KG sample audit completed")
    logger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

