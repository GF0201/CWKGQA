#!/usr/bin/env python3
"""Export case studies from per-sample results into a Markdown report."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import load_jsonl  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser(description="Export case studies from per_sample_results.jsonl")
    parser.add_argument(
        "--run_dir",
        type=str,
        default=None,
        help="Run directory under runs/ (path or name); mutually exclusive with --run-id",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Run ID (e.g. real_dev3_task3_fix1); resolved to runs/<run-id>",
    )
    parser.add_argument(
        "--top-k",
        "--topk",
        dest="top_k",
        type=int,
        default=5,
        help="Number of cases per (status,error_type) group",
    )
    args = parser.parse_args()

    if args.run_id and args.run_dir:
        raise SystemExit("Cannot specify both --run-id and --run_dir")
    if not args.run_id and not args.run_dir:
        raise SystemExit("Must specify --run-id or --run_dir")

    run_dir = Path(args.run_dir) if args.run_dir else ROOT / "runs" / args.run_id
    if not run_dir.is_absolute():
        run_dir = ROOT / "runs" / run_dir
    artifacts_dir = run_dir / "artifacts"
    per_sample_path = artifacts_dir / "per_sample_results.jsonl"
    if not per_sample_path.exists():
        raise FileNotFoundError(f"{per_sample_path} not found")

    per_sample = load_jsonl(per_sample_path)

    groups: Dict[str, List[Dict]] = defaultdict(list)
    for rec in per_sample:
        status = rec.get("status", "unknown")
        err = rec.get("error_type") or "none"
        key = f"status={status}, error_type={err}"
        groups[key].append(rec)

    case_md_path = artifacts_dir / "case_studies.md"
    warnings: List[str] = []

    lines: List[str] = []
    lines.append("## Case Studies")
    lines.append("")
    lines.append(f"- Run directory: `{run_dir}`")
    lines.append(f"- Source file: `{per_sample_path}`")
    lines.append("")

    if warnings:
        lines.append("### Warnings")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    for group_name, recs in sorted(groups.items()):
        # Skip the fully successful group if there are other groups; keep it if it's the only group.
        if group_name.startswith("status=ok") and len(groups) > 1:
            continue
        lines.append(f"### Group: {group_name}")
        lines.append("")
        top_k = min(args.top_k, len(recs))
        for idx, rec in enumerate(recs[:top_k], start=1):
            qid = rec.get("qid", "")
            question = rec.get("question", "")
            status = rec.get("status", "")
            error_type = rec.get("error_type") or "none"
            http_status = rec.get("http_status")
            trace_path = rec.get("trace_path") or "N/A"
            if rec.get("trace_path") is None:
                warnings.append(f"Missing trace_path for qid={qid}")

            lines.append(f"{idx}. `qid={qid}`")
            lines.append(f"   - **question**: {question}")
            lines.append(f"   - **status**: `{status}`")
            lines.append(f"   - **error_type**: `{error_type}`")
            lines.append(f"   - **http_status**: `{http_status}`")
            lines.append(f"   - **trace_path**: `{trace_path}`")
            lines.append("")

    # If any warnings were collected late (e.g. missing trace_path), add a section at the end.
    if warnings:
        lines.append("### Warnings (generated while exporting)")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    case_md_path.parent.mkdir(parents=True, exist_ok=True)
    case_md_path.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

