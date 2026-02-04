from __future__ import annotations

"""Utility helpers for paths and I/O used by experiment scripts."""

from pathlib import Path
from typing import Any, Iterable, List
import sys

from . import ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import load_jsonl as _core_load_jsonl, save_jsonl as _core_save_jsonl, load_json, save_json  # type: ignore


DATASETS_DIR = ROOT / "datasets"
RUNS_DIR = ROOT / "runs"
REPORTS_DIR = ROOT / "reports"


def resolve(path: str | Path) -> Path:
    """Resolve a repo-relative or absolute path to an absolute Path."""
    p = Path(path)
    if p.is_absolute():
        return p
    return ROOT / p


def ensure_dir(path: str | Path) -> Path:
    """Make sure the directory exists and return it as Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_jsonl(path: str | Path) -> List[dict]:
    """Thin wrapper around core.load_jsonl with repo-relative paths support."""
    return list(_core_load_jsonl(resolve(path)))


def save_jsonl(rows: Iterable[dict], path: str | Path) -> None:
    """Thin wrapper around core.save_jsonl with repo-relative paths support."""
    _core_save_jsonl(list(rows), resolve(path))


__all__ = [
    "ROOT",
    "DATASETS_DIR",
    "RUNS_DIR",
    "REPORTS_DIR",
    "resolve",
    "ensure_dir",
    "load_jsonl",
    "save_jsonl",
    "load_json",
    "save_json",
]

