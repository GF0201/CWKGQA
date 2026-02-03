#!/usr/bin/env python3
"""Generate a structured run report MD from runs/<run_id>/ disk files.

Report is written to reports/YYYYMMDD_<task_name>__<run_id>.md by default.
Idempotent: overwrites same out path.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import load_json, load_jsonl  # type: ignore

REPORTS_DIR = ROOT / "reports"
RUN_LOG_TAIL_LINES = 80


def _normalize_task_name(s: str) -> str:
    return re.sub(r"[- ]+", "_", s.strip()).strip("_") or "run"


def _date_from_manifest(manifest: dict) -> str:
    start = manifest.get("start_time") or ""
    if start:
        try:
            return start[:10].replace("-", "")
        except Exception:
            pass
    return datetime.now().strftime("%Y%m%d")


def _group_input_sha256(manifest: dict) -> dict[str, list[tuple[str, str]]]:
    inp = manifest.get("input_files_sha256") or {}
    groups: dict[str, list[tuple[str, str]]] = {"DATA::": [], "OLD::": [], "NEW::": []}
    for k, v in inp.items():
        if k.startswith("DATA::"):
            groups["DATA::"].append((k, v))
        elif k.startswith("OLD::"):
            groups["OLD::"].append((k, v))
        else:
            groups["NEW::"].append((k, v))
    return groups


def _count_failures_csv(failures_path: Path) -> tuple[int, int, list[tuple[str, int]]]:
    """Return (total_lines_including_header, failure_rows, error_type_counts).

    total_lines_including_header = file line count (行数)
    failure_rows = max(0, total_lines_including_header - 1), only data rows (不含表头)
    error_type_counts = Counter of error_type column over failure_rows only (top 10)
    """
    if not failures_path.exists():
        return 0, 0, []
    total_lines_including_header = _count_lines(failures_path) or 0
    failure_rows = max(0, total_lines_including_header - 1)

    rows: list[list[str]] = []
    col = -1
    with open(failures_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        if header:
            try:
                col = header.index("error_type")
            except ValueError:
                col = 5 if len(header) > 5 else -1
        for row in reader:
            if row:
                rows.append(row)
    if col < 0 or not rows:
        return total_lines_including_header, failure_rows, []
    c: Counter[str] = Counter()
    for row in rows:
        if len(row) > col and row[col].strip():
            c[row[col].strip()] += 1
        else:
            c["(empty)"] += 1
    return total_lines_including_header, failure_rows, c.most_common(10)


def _count_lines(path: Path) -> int | None:
    if not path.exists():
        return None
    n = 0
    with open(path, "r", encoding="utf-8") as f:
        for _ in f:
            n += 1
            if n > 1_000_000:
                return n
    return n


def _read_run_log_tail(path: Path, last_n: int = RUN_LOG_TAIL_LINES) -> list[str]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return lines[-last_n:] if len(lines) > last_n else lines


def generate_report(run_id: str, task_name: str, out_path: Path | None = None) -> Path:
    run_dir = ROOT / "runs" / run_id
    task_slug = _normalize_task_name(task_name)

    manifest_path = run_dir / "repro_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"MISSING: {manifest_path}")

    manifest = load_json(manifest_path)
    date_str = _date_from_manifest(manifest)
    if out_path is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = REPORTS_DIR / f"{date_str}_{task_slug}__{run_id}.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    metrics_path = run_dir / "metrics.json"
    metrics: dict | None = load_json(metrics_path) if metrics_path.exists() else None

    artifacts_dir = run_dir / "artifacts"
    per_sample_path = artifacts_dir / "per_sample_results.jsonl"
    failures_path = artifacts_dir / "failures.csv"
    case_studies_path = artifacts_dir / "case_studies.md"
    kg_audit_csv = artifacts_dir / "kg_sample_audit.csv"
    kg_audit_summary = artifacts_dir / "kg_sample_audit_summary.json"
    run_log_path = run_dir / "run.log"

    # Input fingerprint groups (first N per group)
    groups = _group_input_sha256(manifest)
    total_inputs = sum(len(g) for g in groups.values())

    # Failures stats
    failures_total_lines, failures_data_rows, error_type_counts = _count_failures_csv(failures_path)

    # Line counts
    per_sample_lines = _count_lines(per_sample_path)
    run_log_tail = _read_run_log_tail(run_log_path)

    # Validate: infer from run.log (source must be verifiable)
    validate_status = "N/A"
    validate_source = "no validate log found"
    log_text = "".join(run_log_tail)
    if "validate_audit_artifacts: PASS" in log_text:
        validate_status = "PASS"
        validate_source = "run.log contains 'validate_audit_artifacts: PASS'"
    elif "validate_audit_artifacts: FAIL" in log_text:
        validate_status = "FAIL"
        validate_source = "run.log contains 'validate_audit_artifacts: FAIL'"
    elif "Validated audit artifacts" in log_text:
        validate_status = "PASS"
        validate_source = "run.log contains 'Validated audit artifacts'"
    elif "Validated metrics" in log_text:
        validate_status = "PASS"
        validate_source = "run.log contains 'Validated metrics'"

    args = manifest.get("args") or {}
    phase = manifest.get("phase") or ""
    mode = args.get("mode") or ""
    seed = manifest.get("seed") or args.get("seed") or ""
    no_cache = args.get("no_cache")
    subprocess_rc = manifest.get("subprocess_return_code")

    # Metrics summary
    total_em = total_f1 = None
    exec_em = exec_f1 = None
    em_f1_note = ""
    if metrics:
        t = metrics.get("total") or {}
        e = metrics.get("executable_or_answerable") or {}
        total_em = t.get("EM")
        total_f1 = t.get("F1")
        exec_em = e.get("EM")
        exec_f1 = e.get("F1")
        if total_em is None or total_f1 is None:
            em_f1_note = "未计算，原因见 warnings"

    lines: list[str] = []
    lines.append(f"# Run Report: {task_name} / {run_id}")
    lines.append("")
    lines.append("## 1. 基本信息")
    lines.append("")
    lines.append(f"- **start_time**: {manifest.get('start_time', 'N/A')}")
    lines.append(f"- **end_time**: {manifest.get('end_time', 'N/A')}")
    lines.append(f"- **phase**: {phase}")
    lines.append(f"- **mode**: {mode}")
    lines.append(f"- **seed**: {seed}")
    lines.append(f"- **no_cache**: {no_cache}")
    lines.append(f"- **subprocess_return_code**: {subprocess_rc}")
    lines.append(f"- **runner_name / task_name**: {task_name}")
    lines.append("")

    lines.append("## 2. 命令")
    lines.append("")
    argv = manifest.get("command_argv") or []
    lines.append("```")
    lines.append(" ".join(argv))
    lines.append("```")
    sub_cmd = manifest.get("subprocess_command_line")
    if sub_cmd:
        lines.append("")
        lines.append("**subprocess_command_line**:")
        lines.append("```")
        lines.append(sub_cmd)
        lines.append("```")
    lines.append("")

    lines.append("## 3. 输入指纹 (input_files_sha256)")
    lines.append("")
    lines.append(f"总数: {total_inputs}")
    lines.append("")
    for label, key_vals in [("DATA::", groups["DATA::"]), ("OLD::", groups["OLD::"]), ("NEW::", groups["NEW::"])]:
        lines.append(f"### {label}")
        for k, v in key_vals:
            lines.append(f"- `{k}`: `{v}`")
        if not key_vals:
            lines.append("(无)")
        lines.append("")

    lines.append("## 4. 关键产物索引")
    lines.append("")
    for name, p in [
        ("repro_manifest.json", manifest_path),
        ("metrics.json", metrics_path),
        ("artifacts/per_sample_results.jsonl", per_sample_path),
        ("artifacts/failures.csv", failures_path),
        ("artifacts/case_studies.md", case_studies_path),
        ("artifacts/kg_sample_audit.csv", kg_audit_csv),
        ("artifacts/kg_sample_audit_summary.json", kg_audit_summary),
        ("run.log", run_log_path),
    ]:
        if p.exists():
            extra = ""
            if p == per_sample_path and per_sample_lines is not None:
                extra = f" ({per_sample_lines} 行)"
            elif p == failures_path:
                extra = f" (header=1, failure_rows={failures_data_rows})"
            lines.append(f"- **{name}**: `{p}`{extra}")
        else:
            lines.append(f"- **{name}**: MISSING: `{p}`")
    lines.append("")

    lines.append("## 5. 指标摘要 (metrics.json)")
    lines.append("")
    if metrics:
        lines.append("| 层级 | n | EM | F1 |")
        lines.append("|------|---|----|----|")
        t = metrics.get("total") or {}
        e = metrics.get("executable_or_answerable") or {}
        lines.append(f"| total | {t.get('n', '')} | {total_em if total_em is not None else 'null'} | {total_f1 if total_f1 is not None else 'null'} |")
        lines.append(f"| executable_or_answerable | {e.get('n', '')} | {exec_em if exec_em is not None else 'null'} | {exec_f1 if exec_f1 is not None else 'null'} |")
        if em_f1_note:
            lines.append("")
            lines.append(f"**说明**: {em_f1_note}")
    else:
        lines.append("MISSING: metrics.json")
    lines.append("")

    lines.append("## 6. 校验结果")
    lines.append("")
    lines.append(f"- **validate_audit_artifacts**: {validate_status}")
    lines.append(f"- **来源**: {validate_source}")
    lines.append("")

    lines.append("## 7. Warnings")
    lines.append("")
    warnings = manifest.get("warnings") or []
    if warnings:
        for w in warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- (无)")
    lines.append("")

    lines.append("## 8. failures.csv 按 error_type 计数 (top 10)")
    lines.append("")
    if error_type_counts:
        for et, cnt in error_type_counts:
            lines.append(f"- `{et}`: {cnt}")
    elif failures_path.exists() and failures_data_rows == 0:
        lines.append("- 无失败行（表头+0行数据）")
    else:
        lines.append("- (文件不存在)")
    lines.append("")

    lines.append("## 9. run.log 末尾 80 行")
    lines.append("")
    lines.append("```")
    for line in run_log_tail:
        lines.append(line.rstrip())
    lines.append("```")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate run report MD")
    parser.add_argument("--run-id", type=str, required=True, help="Run ID (e.g. domain_main_smoke1)")
    parser.add_argument("--task-name", type=str, required=True, help="Task name (e.g. task4_domain_main_smoke)")
    parser.add_argument("--out", type=str, default=None, help="Output path; default reports/YYYYMMDD_<task>__<run_id>.md")
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else None
    try:
        p = generate_report(args.run_id, args.task_name, out_path)
        print(p)
        return 0
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
