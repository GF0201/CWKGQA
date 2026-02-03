#!/usr/bin/env python3
"""Run LC-QuAD2 dev200 (or subset) experiment.

Outputs runs/<id>/{repro_manifest.json,metrics.json,run.log,artifacts/...}.
"""
import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import (
    set_seed,
    DualLogger,
    write_repro_manifest,
    save_metrics,
    make_two_level_metrics,
    save_jsonl,
    validate_metrics,
    validate_audit_artifacts,
)

OLD_DIR = Path(r"C:\Users\顾北上\KGELLM\kgqa-thesis")
TASK_NAME = "task3_lcquad2_dev200"


def main():
    parser = argparse.ArgumentParser(description="Run LC-QuAD2 dev experiment")
    parser.add_argument("--data_file", type=str, required=True, help="Path to unified_dev.jsonl")
    parser.add_argument("--old_dir", type=str, default=str(OLD_DIR), help="Path to kgqa-thesis (for real pipeline)")
    parser.add_argument("--limit", type=int, default=10, help="Sample limit (e.g. 200 for dev200)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-cache", action="store_true", help="Disable cache (for paper experiments)")
    parser.add_argument("--mock", action="store_true", help="Force minimal mock (no old pipeline)")
    parser.add_argument(
        "--output-id",
        type=str,
        default=None,
        help="Custom run_id under runs/; default: lcquad2_dev<limit>_<timestamp>",
    )
    args = parser.parse_args()

    set_seed(args.seed)
    data_file = Path(args.data_file)
    old_dir = Path(args.old_dir)

    exp_id = args.output_id or f"lcquad2_dev{args.limit}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = ROOT / "runs" / exp_id
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = DualLogger(run_dir, "run.log")
    start_time = datetime.now().isoformat()

    logger.log(f"argv: {' '.join(sys.argv)}")
    logger.log("LC-QuAD2 dev run started")
    logger.log(f"Run dir: {run_dir}")
    logger.log(f"Data: {data_file}")
    logger.log(f"Limit: {args.limit}")
    logger.log(f"old_dir: {old_dir}")

    from datasets.lcquad2_wdqs.runner import run_old_pipeline, run_minimal_mock

    use_old = not args.mock and old_dir.exists() and (old_dir / "scripts" / "40_run_pipeline.py").exists()
    argv = list(sys.argv)

    # Inputs for hashing: data file, NEW_DIR requirements, config, this script, and OLD_DIR key files if real mode
    inputs = [
        data_file,
        ROOT / "requirements.txt",
        ROOT / "configs" / "default.yaml",
        ROOT / "scripts" / "run_lcquad2_dev200.py",
    ]
    if use_old:
        inputs.extend(
            [
                old_dir / "scripts" / "40_run_pipeline.py",
                old_dir / "configs" / "subsets.yaml",
                old_dir / "configs" / "datasets" / "lcquad2.yaml",
                old_dir / "configs" / "runs" / "lcquad2_baseline.yaml",
            ]
        )

    args_dict = {
        "old_dir": str(old_dir),
        "data_file": str(data_file),
        "limit": args.limit,
        "seed": args.seed,
        "no_cache": bool(args.no_cache),
        "mock": bool(args.mock),
        "output_id": args.output_id,
        "mode": "mock" if args.mock or not use_old else "real",
    }

    # --- Pre-run manifest for real mode ---
    if use_old and data_file.exists():
        pre_manifest = write_repro_manifest(
            run_dir,
            run_id=exp_id,
            start_time=start_time,
            end_time=start_time,
            command_argv=argv,
            seed=args.seed,
            inputs=inputs,
            config_dict={},
            args=args_dict,
            warnings=[],
            old_dir=old_dir,
            data_file=data_file,
            extra_fields={"phase": "pre_run"},
        )
        logger.log("Pre-run manifest saved")
    else:
        pre_manifest = None  # 未使用，仅占位

    # --- 调用旧管线或 mock ---
    old_run_dir = None
    subprocess_cmd = []
    return_code = 0
    error_message = None
    try:
        if use_old and data_file.exists():
            preds, metrics_raw, old_run_dir, return_code, error_message, subprocess_cmd = run_old_pipeline(
                old_dir, data_file, args.limit, args.seed, args.no_cache, logger.log
            )
            n = len(preds)
            if return_code != 0 or error_message:
                # 视为失败，使用占位 metrics（EM/F1 缺失用 null）
                total = {"n": args.limit, "EM": None, "F1": None}
                exec_ok = {"n": 0, "EM": None, "F1": None}
                cov = {"n": args.limit, "ratio": 0.0}
                metrics = make_two_level_metrics(total, exec_ok, cov)
                metrics["error_summary"] = {
                    "stage": "subprocess",
                    "return_code": return_code,
                    "message": error_message,
                }
            else:
                # 正常成功，包一层 two-level。Option A：EM/F1 缺失则 null，不填 0
                em_val = metrics_raw.get("EM")
                f1_val = metrics_raw.get("F1")
                if em_val is None and f1_val is None:
                    # 旧管线无 EM/F1，按方案 A 记 null
                    em_val = None
                    f1_val = None
                total = {
                    "n": n,
                    "EM": em_val,
                    "F1": f1_val,
                    "avg_wdqs_calls": metrics_raw.get("avg_wdqs_calls", 0.0),
                }
                exec_ok = {"n": n, "EM": em_val, "F1": f1_val}
                cov = {"n": n, "ratio": 1.0 if n > 0 else 0.0}
                metrics = make_two_level_metrics(total, exec_ok, cov)
            save_jsonl(preds, run_dir / "predictions.jsonl")
        else:
            # mock 模式或找不到 old_dir/data_file
            if not data_file.exists():
                logger.log("Data file not found, creating dummy run")
            logger.log(f"Using minimal mock (old_dir exists={old_dir.exists()}, mock={args.mock})")
            preds, metrics = run_minimal_mock(data_file, args.limit, logger.log)
            save_jsonl(preds, run_dir / "predictions.jsonl")
            if "total" not in metrics or not isinstance(metrics.get("total"), dict):
                n = len(preds)
                total = {"n": n, "EM": 0.0, "F1": 0.0}
                exec_ok = {"n": n, "EM": 0.0, "F1": 0.0}
                cov = {"n": n, "ratio": 1.0 if n > 0 else 0.0}
                metrics = make_two_level_metrics(total, exec_ok, cov)
    except Exception as e:  # 防御：任何异常都视为失败但继续落盘产物
        error_message = f"run_lcquad2_dev200 error: {e!r}"
        logger.log(error_message)
        preds = [{"id": f"sample_{i}", "question": "", "_error": True} for i in range(args.limit)]
        save_jsonl(preds, run_dir / "predictions.jsonl")
        total = {"n": args.limit, "EM": None, "F1": None}
        exec_ok = {"n": 0, "EM": None, "F1": None}
        cov = {"n": args.limit, "ratio": 0.0}
        metrics = make_two_level_metrics(total, exec_ok, cov)
        metrics["error_summary"] = {
            "stage": "wrapper",
            "return_code": return_code,
            "message": error_message,
        }

    # Save metrics and validate
    save_metrics(metrics, run_dir / "metrics.json")
    logger.log("Saved metrics.json")
    validate_metrics(metrics)
    logger.log("Validated metrics.json")

    # Artifacts: per-sample results + failures.csv
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    per_sample = []
    old_run_dir_str = str(old_run_dir) if use_old and old_run_dir else None
    # 若 preds 为空且需要失败记录，则根据 limit 造占位 qid
    if not preds and args.limit:
        preds = [{"id": f"sample_{i}", "question": "", "_error": True} for i in range(args.limit)]

    # Option A: em/f1 缺失则记为 null，error_type=metric_missing
    metric_missing = (
        metrics.get("total", {}).get("EM") is None
        or metrics.get("total", {}).get("F1") is None
    )
    manifest_warnings = []

    for p in preds:
        status = "ok"
        error_type = None
        if metrics.get("error_summary"):
            status = "fail"
            error_type = metrics["error_summary"].get("stage")
        elif p.get("_error"):
            status = "fail"
            error_type = "error"
        elif p.get("_skipped_timeout"):
            status = "fail"
            error_type = "timeout"
        elif metric_missing:
            status = "metric_missing"
            error_type = "metric_missing"

        # is_executable: 成功完成且无 subprocess 错误则 True（占位）
        is_exec = not metrics.get("error_summary") and status not in ("fail",)
        record = {
            "qid": p.get("id", ""),
            "question": str(p.get("question", ""))[:120],
            "status": status,
            "is_executable": is_exec,
            "http_status": None,
            "error_type": error_type,
            "em": None,
            "f1": None,
            "trace_path": old_run_dir_str,
        }
        per_sample.append(record)

    if metric_missing:
        manifest_warnings.append(
            "metric_missing: em/f1 not computed; leaving as null"
        )

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
            if r["status"] not in ("fail", "metric_missing"):
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

    validate_audit_artifacts(metrics, per_sample, failures_path)
    logger.log("Validated audit artifacts")

    end_time = datetime.now().isoformat()

    # --- Post-run manifest（无论成功失败都更新）---
    extra_fields = {
        "phase": "post_run",
        "subprocess_return_code": return_code,
    }
    if use_old:
        extra_fields["subprocess_command_argv"] = subprocess_cmd
        extra_fields["subprocess_command_line"] = " ".join(subprocess_cmd)
        extra_fields["subprocess_seed"] = args.seed
        if old_run_dir:
            extra_fields["subprocess_run_id"] = old_run_dir.name
            extra_fields["subprocess_run_dir"] = str(old_run_dir.resolve())

    all_warnings = list(manifest_warnings)
    if error_message:
        all_warnings.append(error_message)

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
        warnings=all_warnings,
        old_dir=old_dir if use_old else None,
        data_file=data_file,
        extra_fields=extra_fields,
    )
    logger.log("Saved repro_manifest.json")
    logger.log(
        f"Inputs hashed: {len(manifest.get('input_files_sha256', {}))}; "
        f"first_keys={list(manifest.get('input_files_sha256', {}).keys())[:3]}"
    )
    logger.log("Run completed")
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
        run_id_for_report = None
    finally:
        if run_id_for_report:
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("gen_run_report", ROOT / "scripts" / "gen_run_report.py")
                gen_run_report = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(gen_run_report)
                out_path = gen_run_report.generate_report(run_id_for_report, TASK_NAME)
                run_log_path = ROOT / "runs" / run_id_for_report / "run.log"
                if run_log_path.exists():
                    with open(run_log_path, "a", encoding="utf-8") as f:
                        f.write(f"Report saved to {out_path}\n")
                out_path = gen_run_report.generate_report(run_id_for_report, TASK_NAME)
                print(f"Report: {out_path}")
            except Exception as e:
                print(f"gen_run_report: {e}", file=sys.stderr)
    sys.exit(exit_code)
