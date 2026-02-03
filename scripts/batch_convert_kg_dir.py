#!/usr/bin/env python3
"""Batch convert extracted_jsons/*.json (head/connect/tail) to unified KG.

- Per-file: per_file/<stem>.jsonl, <stem>.tsv, <stem>_report.json
- Merged: merged/triples.jsonl, merged/triples.tsv
- Summary: artifacts/kg_merge_report.json

Unified schema: subject (=head), predicate (=connect), object (=tail).
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

from core import load_json, save_json, save_jsonl  # type: ignore


def _normalize(s: str) -> str:
    return (s or "").strip()


def _load_json_safe(path: Path, encoding: str = "utf-8") -> list:
    for enc in (encoding, "utf-8-sig"):
        try:
            with open(path, "r", encoding=enc) as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    raise ValueError(f"Failed to load {path}")


def process_one_file(
    inp_path: Path,
    out_jsonl: Path,
    out_tsv: Path,
    out_report: Path,
    encoding: str = "utf-8",
) -> dict:
    """Process one JSON file → jsonl, tsv, report. Return per-file stats."""
    raw = _load_json_safe(inp_path, encoding)
    if not isinstance(raw, list):
        raw = [raw] if raw else []

    kept: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    empty_filtered = 0

    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            empty_filtered += 1
            continue
        head = _normalize(item.get("head", ""))
        connect = _normalize(item.get("connect", ""))
        tail = _normalize(item.get("tail", item.get("object", "")))
        if not head and not connect and not tail:
            empty_filtered += 1
            continue
        key = (head, connect, tail)
        if key in seen:
            continue
        seen.add(key)
        kept.append({
            "subject": head,
            "predicate": connect,
            "object": tail,
            "source_row": i,
        })

    # Write jsonl
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Write tsv
    with open(out_tsv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["subject", "predicate", "object", "source_row"])
        for r in kept:
            w.writerow([r["subject"], r["predicate"], r["object"], r["source_row"]])

    report = {
        "source_file": inp_path.name,
        "n_raw": len(raw),
        "n_kept": len(kept),
        "n_dedup": len(kept),
        "empty_filtered": empty_filtered,
    }
    save_json(report, out_report)
    return report


def merge_all(
    per_file_dir: Path,
    merged_dir: Path,
    dedup: bool = True,
) -> tuple[list[dict], dict]:
    """Merge all per_file/*.jsonl into triples.jsonl/tsv. Return (triples, merge_report)."""
    merged_dir.mkdir(parents=True, exist_ok=True)
    all_triples: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    per_file_stats: list[dict] = []
    pred_counter: Counter[str] = Counter()
    head_counter: Counter[str] = Counter()

    jsonl_files = sorted(per_file_dir.glob("*.jsonl"))
    for jf in jsonl_files:
        stem = jf.stem
        n_from_file = 0
        with open(jf, "r", encoding="utf-8") as f:
            for row_idx, line in enumerate(f):
                if not line.strip():
                    continue
                obj = json.loads(line)
                subj = _normalize(obj.get("subject", obj.get("head", "")))
                pred = _normalize(obj.get("predicate", obj.get("connect", "")))
                obj_val = _normalize(obj.get("object", obj.get("tail", "")))
                if not subj and not pred and not obj_val:
                    continue
                key = (subj, pred, obj_val)
                if dedup and key in seen:
                    continue
                seen.add(key)
                rec = {
                    "subject": subj,
                    "predicate": pred,
                    "object": obj_val,
                    "source_file": stem,
                    "source_row": obj.get("source_row", row_idx),
                }
                all_triples.append(rec)
                n_from_file += 1
                pred_counter[pred] += 1
                head_counter[subj] += 1
        per_file_stats.append({"file": stem, "n_merged": n_from_file})

    # Rebuild sid 0..N-1
    for sid, r in enumerate(all_triples):
        r["sid"] = sid
        r["triple_id"] = str(sid)

    # Write triples.jsonl
    out_jsonl = merged_dir / "triples.jsonl"
    save_jsonl(all_triples, out_jsonl)

    # Write triples.tsv (subject, predicate, object, sid, source_file, source_row)
    out_tsv = merged_dir / "triples.tsv"
    with open(out_tsv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["triple_id", "subject", "predicate", "object", "source_file", "source_row"])
        for r in all_triples:
            w.writerow([
                r["triple_id"],
                r["subject"],
                r["predicate"],
                r["object"],
                r["source_file"],
                r["source_row"],
            ])

    merge_report = {
        "n_files": len(jsonl_files),
        "per_file_stats": per_file_stats,
        "n_kept": len(all_triples),
        "n_dedup": len(all_triples),
        "top_predicates": pred_counter.most_common(20),
        "top_heads": head_counter.most_common(20),
    }
    return all_triples, merge_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch convert extracted_jsons to unified KG")
    parser.add_argument(
        "--input_dir",
        type=str,
        default=None,
        help="Input dir (default: extracted_jsons)",
    )
    parser.add_argument(
        "--out_dir",
        type=str,
        default="datasets/domain_main_kg",
        help="Output root dir",
    )
    parser.add_argument("--seed", type=int, default=42, help="Seed for reproducibility")
    parser.add_argument("--dedup", type=str, default="true", help="Enable global dedup")
    parser.add_argument("--max_files", type=int, default=None, help="Max files to process (debug)")
    parser.add_argument("--encoding", type=str, default="utf-8")
    args = parser.parse_args()

    inp_dir = Path(args.input_dir or str(ROOT / "extracted_jsons"))
    out_root = ROOT / args.out_dir
    per_file_dir = out_root / "processed" / "per_file"
    merged_dir = out_root / "processed" / "merged"
    artifacts_dir = out_root / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    dedup = str(args.dedup).lower() in ("true", "1", "yes")

    json_files = sorted(inp_dir.glob("*.json"))
    if args.max_files is not None:
        json_files = json_files[: args.max_files]

    if not json_files:
        print(f"No *.json in {inp_dir}", file=sys.stderr)
        return 1

    # Per-file processing
    all_reports: list[dict] = []
    for jf in json_files:
        stem = jf.stem
        out_j = per_file_dir / f"{stem}.jsonl"
        out_t = per_file_dir / f"{stem}.tsv"
        out_r = per_file_dir / f"{stem}_report.json"
        rep = process_one_file(jf, out_j, out_t, out_r, args.encoding)
        all_reports.append(rep)
        print(f"  {stem}: n_raw={rep['n_raw']}, n_kept={rep['n_kept']}")

    # Merge
    triples, merge_report = merge_all(per_file_dir, merged_dir, dedup)
    merge_report["per_file_reports"] = all_reports
    merge_report["n_raw_total"] = sum(r["n_raw"] for r in all_reports)

    report_path = artifacts_dir / "kg_merge_report.json"
    save_json(merge_report, report_path)
    print(f"Merged {len(triples)} triples; report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
