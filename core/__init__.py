"""Core modules for reproducible experiments."""
from .seed import set_seed
from .logging import DualLogger
from .repro import write_repro_manifest
from .io import load_json, save_json, load_jsonl, save_jsonl
from .metrics import (
    make_two_level_metrics,
    save_metrics,
    validate_metrics,
    validate_audit_artifacts,
)
from .stats import bootstrap_ci, paired_bootstrap_delta, mcnemar_test

__all__ = [
    "set_seed",
    "DualLogger",
    "write_repro_manifest",
    "load_json",
    "save_json",
    "load_jsonl",
    "save_jsonl",
    "make_two_level_metrics",
    "save_metrics",
    "validate_metrics",
    "validate_audit_artifacts",
    "bootstrap_ci",
    "paired_bootstrap_delta",
    "mcnemar_test",
]
