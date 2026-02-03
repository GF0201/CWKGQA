#!/usr/bin/env python3
"""Generate read-only audit of OLD_DIR (kgqa-thesis). Output to NEW_DIR/_audit_old/."""
import hashlib
import subprocess
import sys
from pathlib import Path
from datetime import datetime

OLD_DIR = Path(r"C:\Users\顾北上\KGELLM\kgqa-thesis")
AUDIT_DIR = Path(__file__).resolve().parent.parent / "_audit_old"

# Key file patterns to include (relative to OLD_DIR)
INCLUDE_PATTERNS = (
    "**/*.py",
    "**/*.yaml",
    "**/*.yml",
    "**/*.json",
    "**/*.jsonl",
    "**/*.md",
    "**/*.txt",
    "**/MANIFEST.json",
)
EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv", "data/cache"}


def file_rel(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_files(base: Path) -> list[Path]:
    files = []
    for pattern in INCLUDE_PATTERNS:
        for p in base.glob(pattern):
            if not p.is_file():
                continue
            if any(ex in p.parts for ex in EXCLUDE_DIRS):
                continue
            files.append(p)
    return sorted(set(files))


def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # --- file_manifest.tsv ---
    manifest_path = AUDIT_DIR / "file_manifest.tsv"
    files = collect_files(OLD_DIR)
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("path\tsize\tmtime\tsha256\n")
        for p in files:
            try:
                st = p.stat()
                rel = file_rel(p, OLD_DIR)
                sha = sha256_file(p)
                mtime = datetime.fromtimestamp(st.st_mtime).isoformat()
                f.write(f"{rel}\t{st.st_size}\t{mtime}\t{sha}\n")
            except OSError as e:
                f.write(f"{file_rel(p, OLD_DIR)}\t-1\t-\t{repr(e)}\n")
    print(f"Wrote {manifest_path} ({len(files)} files)")

    # --- env_snapshot.txt ---
    env_path = AUDIT_DIR / "env_snapshot.txt"
    lines = [f"Generated: {datetime.now().isoformat()}", ""]
    try:
        lines.append(subprocess.check_output([sys.executable, "--version"], text=True).strip())
    except Exception as e:
        lines.append(f"python --version: {e}")
    lines.append("")
    try:
        lines.append(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True))
    except Exception as e:
        try:
            lines.append(subprocess.check_output(["pip", "freeze"], text=True))
        except Exception as e2:
            lines.append(f"pip freeze: {e}, {e2}")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {env_path}")

    # --- run_commands.txt ---
    cmd_path = AUDIT_DIR / "run_commands.txt"
    run_commands = """# Key run commands from old experiment (kgqa-thesis)
# Source: experiment_trace_summary.md, PREPROCESS_COMMANDS.md

# Download data
python scripts/10_download_data.py --dataset lcquad2

# Preprocess
python scripts/20_preprocess.py --dataset lcquad2 --out data/processed/unified/ --seed 42

# Smoke graph builder
python scripts/45_smoke_graph_builder.py --seed 42 --max_samples 10 --no-cache

# Phase 9 baseline (dev200)
python scripts/52_run_phase9_experiment.py --run_tag baseline --config configs/runs/lcquad2_baseline.yaml --split dev --limit 200 --seed 42 --no-cache

# Phase 9 phase8 (with subgraph)
python scripts/52_run_phase9_experiment.py --run_tag phase8 --config configs/runs/lcquad2_phase8.yaml --split dev --limit 200 --seed 42 --no-cache

# Pipeline directly
python scripts/40_run_pipeline.py --config configs/runs/lcquad2_baseline.yaml --split dev --limit 20 --seed 42 --no-cache

# M3 significance
python scripts/compute_dev200_significance_canonical.py

# Validate paper outputs
python scripts/62_validate_paper_outputs.py
"""
    with open(cmd_path, "w", encoding="utf-8") as f:
        f.write(run_commands)
    print(f"Wrote {cmd_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
