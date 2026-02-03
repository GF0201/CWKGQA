#!/usr/bin/env python3
"""Smoke test: dummy samples, fixed seed, manifest, metrics, run.log."""
import csv
import sys
from datetime import datetime
from pathlib import Path

# Add project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import (
    set_seed,
    DualLogger,
    write_repro_manifest,
    save_metrics,
    make_two_level_metrics,
    validate_metrics,
    save_jsonl,
)


def main():
    set_seed(42)
    exp_id = f"smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = ROOT / "runs" / exp_id
    run_dir.mkdir(parents=True, exist_ok=True)

    logger = DualLogger(run_dir, "run.log")
    start_time = datetime.now().isoformat()

    logger.log("Smoke test started")
    logger.log(f"Run dir: {run_dir}")

    # Dummy samples (5)
    from datasets.domain_stub.adapter import get_dummy_samples
    samples = get_dummy_samples(5)
    logger.log(f"Processed {len(samples)} dummy samples")

    # Dummy metrics (two-level)
    metrics = make_two_level_metrics(
        total={"n": 5, "EM": 0.0, "F1": 0.0},
        executable_or_answerable={"n": 5, "EM": 0.0, "F1": 0.0},
        coverage_upper_bound={"n": 5, "ratio": 1.0},
    )
    save_metrics(metrics, run_dir / "metrics.json")
    logger.log("Saved metrics.json")

    # Validate metrics to avoid "fake success"
    validate_metrics(metrics)
    logger.log("Validated metrics.json")

    # Per-sample results + failures artifacts
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    per_sample = []
    for s in samples:
        per_sample.append(
            {
                "qid": s.get("id", ""),
                "question": str(s.get("question", ""))[:120],
                "status": "ok",
                "is_executable": True,
                "http_status": None,
                "error_type": None,
                "em": None,
                "f1": None,
                "trace_path": None,
            }
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
        # smoke: 无失败样本，文件为空表头

    end_time = datetime.now().isoformat()
    argv = list(sys.argv)

    inputs = [
        ROOT / "configs" / "default.yaml",
        ROOT / "requirements.txt",
    ]
    args = {"mode": "smoke"}

    manifest = write_repro_manifest(
        run_dir,
        run_id=exp_id,
        start_time=start_time,
        end_time=end_time,
        command_argv=argv,
        seed=42,
        inputs=inputs,
        config_dict={},
        args=args,
        warnings=[],
    )
    logger.log("Saved repro_manifest.json")
    logger.log(
        f"Inputs hashed: {len(manifest.get('input_files_sha256', {}))}; "
        f"first_keys={list(manifest.get('input_files_sha256', {}).keys())[:3]}"
    )

    logger.log("Smoke test completed")
    logger.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
