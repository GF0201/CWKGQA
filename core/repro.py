"""Generate runs/<exp_id>/repro_manifest.json for reproducibility."""
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def get_python_version() -> str:
    return sys.version


def get_pip_freeze() -> str:
    try:
        return subprocess.check_output(
            [sys.executable, "-m", "pip", "freeze"], text=True
        ).strip()
    except Exception:
        return ""


def get_platform_info() -> dict:
    return {
        "os": platform.system(),
        "hostname": socket.gethostname() if hasattr(socket, "gethostname") else "",
        "platform": platform.platform(),
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(text: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def normalize_input_key(
    path: Path,
    project_root: Path,
    old_dir: Optional[Path] = None,
    data_file: Optional[Path] = None,
) -> str:
    """Normalize input key to avoid collisions and make provenance explicit."""
    p = path
    try:
        p = p.resolve()
    except Exception:
        p = path

    # DATA:: for main data file
    if data_file is not None:
        try:
            if p.resolve().samefile(Path(data_file).resolve()):
                return f"DATA::{p.name}"
        except Exception:
            # Fallback: name-based
            if p.name == Path(data_file).name:
                return f"DATA::{p.name}"

    # OLD:: for files under OLD_DIR
    if old_dir is not None:
        try:
            old_dir_resolved = Path(old_dir).resolve()
            if p.is_relative_to(old_dir_resolved):
                rel = p.relative_to(old_dir_resolved).as_posix()
                return f"OLD::{rel}"
        except Exception:
            pass

    # NEW_DIR relative path for files under project_root
    try:
        if p.is_relative_to(project_root):
            return p.relative_to(project_root).as_posix()
    except Exception:
        pass

    # Fallback: basename
    return p.name


def write_repro_manifest(
    run_dir: Path,
    *,
    run_id: str,
    start_time: str,
    end_time: str,
    command_argv: Sequence[str],
    seed: int,
    inputs: Optional[Sequence[os.PathLike | str]] = None,
    config_dict: Optional[Dict[str, Any]] = None,
    args: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
    old_dir: Optional[Path] = None,
    data_file: Optional[Path] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Write a detailed repro manifest and return it.

    - Hashes all `inputs` into input_files_sha256
    - Records full argv and parsed args
    - Adds requirements_sha256 and env_summary
    """
    run_dir = Path(run_dir)
    project_root = run_dir.parent.parent  # NEW_DIR root

    # Collect environment info
    python_version_full = get_python_version()
    pip_freeze = get_pip_freeze()

    # Hash inputs
    input_hashes: Dict[str, str] = {}
    warn_list: List[str] = list(warnings or [])
    for p in inputs or []:
        p = Path(p)
        label = normalize_input_key(p, project_root, old_dir=old_dir, data_file=data_file)
        if not p.exists():
            warn_list.append(f"Input missing: {p}")
            continue
        try:
            input_hashes[label] = _sha256_file(p)
        except Exception as e:  # pragma: no cover - defensive
            warn_list.append(f"Failed to hash {p}: {e!r}")

    # Hash requirements (file preferred, otherwise pip_freeze)
    req_path = project_root / "requirements.txt"
    if req_path.exists():
        try:
            requirements_sha256 = _sha256_file(req_path)
        except Exception as e:  # pragma: no cover
            requirements_sha256 = _sha256_text(pip_freeze)
            warn_list.append(f"Failed to hash requirements.txt: {e!r}")
    else:
        requirements_sha256 = _sha256_text(pip_freeze)

    env_summary = {
        "python_version": python_version_full.split()[0],
        "os": platform.system(),
        "platform": platform.platform(),
    }

    manifest: Dict[str, Any] = {
        "run_id": run_id,
        "start_time": start_time,
        "end_time": end_time,
        "python_version": python_version_full,
        "env_summary": env_summary,
        "pip_freeze": pip_freeze,
        "requirements_sha256": requirements_sha256,
        "command_line": " ".join(command_argv),
        "command_argv": list(command_argv),
        "seed": seed,
        "input_files_sha256": input_hashes,
        "config": config_dict or {},
        "args": args or {},
        "warnings": warn_list,
        "output_dir": str(run_dir),
        "platform": get_platform_info(),
    }

    if extra_fields:
        # extra_fields 可以覆盖/补充顶层字段，例如 phase / subprocess_return_code
        manifest.update(extra_fields)

    manifest_path = Path(run_dir) / "repro_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest
