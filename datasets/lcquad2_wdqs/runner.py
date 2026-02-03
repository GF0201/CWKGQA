"""Run LC-QuAD2 pipeline: either via old experiment subprocess or minimal mock."""
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, Tuple, List, Dict, Any


def load_jsonl(path: Path) -> list:
    data = []
    if not path.exists():
        return data
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def save_jsonl(data: list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def run_old_pipeline(
    old_dir: Path,
    data_file: Path,
    limit: int,
    seed: int,
    no_cache: bool,
    log_fn: Callable[[str], None],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Optional[Path], int, Optional[str]]:
    """Invoke OLD_DIR scripts/40_run_pipeline.py via subprocess.

    Returns (preds, metrics, old_run_dir, return_code, error_message).
    """
    config = old_dir / "configs" / "runs" / "lcquad2_baseline.yaml"
    if not config.exists():
        config = old_dir / "configs" / "runs" / "lcquad2_phase8.yaml"
    if not config.exists():
        config = old_dir / "configs" / "datasets" / "lcquad2.yaml"

    cmd = [
        sys.executable,
        str(old_dir / "scripts" / "40_run_pipeline.py"),
        "--config", str(config),
        "--data_file", str(data_file),
        "--limit", str(limit),
        "--seed", str(seed),
    ]
    if no_cache:
        cmd.append("--no-cache")

    log_fn(f"Running: {' '.join(cmd)}")
    return_code = -1
    error_message: Optional[str] = None
    try:
        # 若旧管线挂住，超时视为失败但仍可落盘本侧产物
        result = subprocess.run(
            cmd,
            cwd=str(old_dir),
            capture_output=True,
            text=True,
            timeout=60,  # 可按需调整
        )
        return_code = result.returncode
        log_fn(result.stdout or "")
        if result.stderr:
            log_fn(f"stderr: {result.stderr}")
        if return_code != 0:
            error_message = f"subprocess exited with code {return_code}"
    except subprocess.TimeoutExpired as e:
        error_message = f"subprocess timeout: {e}"
        log_fn(error_message)
    except Exception as e:  # pragma: no cover - 防御
        error_message = f"subprocess error: {e!r}"
        log_fn(error_message)

    # Find output: old pipeline writes to outputs/runs/run_*
    out_base = old_dir / "outputs" / "runs"
    preds: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}
    latest: Optional[Path] = None
    if out_base.exists():
        run_dirs = sorted(out_base.glob("run_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if run_dirs:
            latest = run_dirs[0]
            preds_path = latest / "preds.jsonl"
            metrics_path = latest / "metrics.json"
            if preds_path.exists():
                preds = load_jsonl(preds_path)
            if metrics_path.exists():
                with open(metrics_path, "r", encoding="utf-8") as f:
                    metrics = json.load(f)
    return preds, metrics, latest, return_code, error_message, cmd


def run_minimal_mock(
    data_file: Path,
    limit: int,
    log_fn: Callable[[str], None],
) -> tuple[list, dict]:
    """Minimal mock: load data, emit dummy preds, compute two-level metrics."""
    if not data_file.exists():
        samples = [{"id": f"dummy_{i}", "question": f"Dummy Q{i}?", "answers": []} for i in range(min(limit, 5))]
    else:
        samples = load_jsonl(data_file)[:limit]
    log_fn(f"Loaded {len(samples)} samples from {data_file}")

    preds = []
    for s in samples:
        preds.append({
            "id": s.get("id", ""),
            "question": s.get("question", ""),
            "gold_answers": s.get("gold_answers", s.get("answers", [])),
            "pred_answers": [],
            "status": "no_entity",
            "wdqs_calls": 0,
        })

    n = len(preds)
    total = {"n": n, "EM": 0.0, "F1": 0.0, "empty_rate": 1.0, "avg_wdqs_calls": 0.0}
    exec_ok = {"n": n, "EM": 0.0, "F1": 0.0}
    cov = {"n": n, "ratio": 1.0}
    metrics = {"total": total, "executable_or_answerable": exec_ok, "coverage_upper_bound": cov}
    return preds, metrics
