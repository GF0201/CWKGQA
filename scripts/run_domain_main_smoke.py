#!/usr/bin/env python3
"""Smoke runner for the generic `domain_main` dataset.

This script exercises the full audit chain (run dir, log, manifest,
per-sample results, failures) without requiring real metrics.
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import (  # type: ignore
    set_seed,
    DualLogger,
    write_repro_manifest,
    save_json,
    save_jsonl,
    load_json,
    load_jsonl,
)
from datasets.domain_main.runner import run_smoke
from datasets.domain_main.validate import validate_dataset

TASK_NAME = "task4_domain_main_smoke"


def validate_audit_artifacts(run_dir: Path) -> tuple[bool, list[str]]:
    """校验 run_dir 下审计产物；返回 (ok, errors)。用于 finally 中写 run.log。"""
    errors: list[str] = []
    artifacts_dir = run_dir / "artifacts"
    per_sample_path = artifacts_dir / "per_sample_results.jsonl"
    failures_path = artifacts_dir / "failures.csv"
    manifest_path = run_dir / "repro_manifest.json"

    if not per_sample_path.exists():
        errors.append("per_sample_results.jsonl missing")
    if not failures_path.exists():
        errors.append("failures.csv missing")
    if not manifest_path.exists():
        errors.append("repro_manifest.json missing")

    if errors:
        return False, errors

    manifest = load_json(manifest_path)
    n_total = (manifest.get("args") or {}).get("n_total")
    if n_total is not None:
        per_sample = load_jsonl(per_sample_path)
        if len(per_sample) != n_total:
            errors.append(
                f"per_sample count ({len(per_sample)}) != n_total ({n_total})"
            )
    return (len(errors) == 0, errors)


def main() -> tuple[int, str]:
    parser = argparse.ArgumentParser(description="Domain-main smoke run")
    parser.add_argument("--data_file", type=str, required=True, help="Path to domain_main dataset (JSONL)")
    parser.add_argument("--limit", type=int, default=3, help="Number of samples for smoke (default 3)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output-id",
        type=str,
        default=None,
        help="Custom run_id under runs/; default: domain_main_smoke_<timestamp>",
    )
    args = parser.parse_args()

    set_seed(args.seed)
    data_file = Path(args.data_file)

    exp_id = args.output_id or f"domain_main_smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = ROOT / "runs" / exp_id
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = DualLogger(run_dir, "run.log")
    start_time = datetime.now().isoformat()

    logger.log(f"argv: {' '.join(sys.argv)}")
    logger.log("domain_main smoke started")
    logger.log(f"Run dir: {run_dir}")
    logger.log(f"Data: {data_file}")
    logger.log(f"Limit: {args.limit}")

    # Dataset-level validation (separate from per-sample runner)
    ok_count, bad_count, bad_path = validate_dataset(data_file)
    logger.log(f"Dataset validation: ok={ok_count}, bad={bad_count}, bad_path={bad_path}")

    # Per-sample smoke run (reuses schema validation per-sample)
    per_sample, summary = run_smoke(data_file, args.limit, args.seed, logger.log)

    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    per_sample_path = artifacts_dir / "per_sample_results.jsonl"
    save_jsonl(per_sample, per_sample_path)

    failures_path = artifacts_dir / "failures.csv"
    with open(failures_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "qid",
                "question",
                "status",
                "is_executable",
                "http_status",
                "error_type",
                "em",
                "f1",
                "trace_path",
            ]
        )
        for r in per_sample:
            if r["status"] == "ok":
                continue
            writer.writerow(
                [
                    r["qid"],
                    r["question"],
                    r["status"],
                    r["is_executable"],
                    r["http_status"],
                    r["error_type"],
                    r["em"],
                    r["f1"],
                    r["trace_path"],
                ]
            )

    end_time = datetime.now().isoformat()
    argv = list(sys.argv)

    inputs = [
        data_file,
        ROOT / "configs" / "default.yaml",
        ROOT / "requirements.txt",
        ROOT / "scripts" / "run_domain_main_smoke.py",
    ]
    args_dict = {
        "data_file": str(data_file),
        "limit": args.limit,
        "seed": args.seed,
        "output_id": args.output_id,
        "mode": "domain_main_smoke",
        "n_total": summary.get("n_total"),
        "n_ok": summary.get("n_ok"),
        "n_bad": summary.get("n_bad"),
    }

    warnings = []
    if bad_count > 0:
        warnings.append(
            f"schema_invalid: bad_count={bad_count}, bad_examples={bad_path}"
        )

    manifest = write_repro_manifest(
        run_dir,
        run_id=exp_id,
        start_time=start_time,
        end_time=end_time,
        command_argv=argv,
        seed=args.seed,
        inputs=inputs,
        config_dict={},
        args=args_dict,
        warnings=warnings,
        old_dir=None,
        data_file=data_file,
        extra_fields={"phase": "post_run", "runner_name": TASK_NAME},
    )
    logger.log("Saved repro_manifest.json")
    logger.log(
        f"Inputs hashed: {len(manifest.get('input_files_sha256', {}))}; "
        f"first_keys={list(manifest.get('input_files_sha256', {}).keys())[:3]}"
    )

    logger.log("domain_main smoke completed")
    logger.close()
    return 0, exp_id


if __name__ == "__main__":
    exit_code = 0
    run_id_for_report = None
    try:
        exit_code, run_id_for_report = main()
    except Exception as e:
        print(e, file=sys.stderr)
        exit_code = 1
        run_id_for_report = None  # may not have created run_dir
    finally:
        if run_id_for_report:
            run_dir = ROOT / "runs" / run_id_for_report
            run_log_path = run_dir / "run.log"
            # 固化 validate_audit_artifacts：写 run.log，失败时更新 manifest.warnings，不阻止报告生成
            validate_ok, validate_errors = validate_audit_artifacts(run_dir)
            if run_log_path.exists():
                with open(run_log_path, "a", encoding="utf-8") as f:
                    if validate_ok:
                        f.write("validate_audit_artifacts: PASS\n")
                    else:
                        f.write(f"validate_audit_artifacts: FAIL ({'; '.join(validate_errors)})\n")
            if not validate_ok:
                manifest_path = run_dir / "repro_manifest.json"
                if manifest_path.exists():
                    manifest = load_json(manifest_path)
                    w = manifest.get("warnings") or []
                    w.append(f"validate_audit_artifacts: FAIL ({'; '.join(validate_errors)})")
                    manifest["warnings"] = w
                    save_json(manifest, manifest_path)
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("gen_run_report", ROOT / "scripts" / "gen_run_report.py")
                gen_run_report = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(gen_run_report)
                out_path = gen_run_report.generate_report(run_id_for_report, TASK_NAME)
                if run_log_path.exists():
                    with open(run_log_path, "a", encoding="utf-8") as f:
                        f.write(f"Report saved to {out_path}\n")
                print(f"Report: {out_path}")
            except Exception as e:
                print(f"gen_run_report: {e}", file=sys.stderr)
    sys.exit(exit_code)

