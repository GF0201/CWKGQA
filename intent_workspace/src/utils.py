"""Utility helpers for intent_workspace (config loading, fingerprint, git, etc.)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml


ROOT = Path(__file__).resolve().parent.parent.parent


def canonical_json(obj: Dict[str, Any]) -> str:
    """Canonical JSON with sorted keys for deterministic fingerprint."""

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"YAML config not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def load_intent_configs(
    defaults_path: Path,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Load defaults + taxonomy + rules into three dicts.

    - defaults: intent_experiment_defaults.yaml
    - taxonomy: intent_taxonomy.yaml
    - rules: intent_rules.yaml
    """

    defaults = load_yaml(defaults_path)

    taxonomy_rel = defaults.get("taxonomy_path", "intent_workspace/configs/intent_taxonomy.yaml")
    rules_rel = defaults.get("rules_path", "intent_workspace/configs/intent_rules.yaml")

    taxonomy_path = (ROOT / taxonomy_rel).resolve()
    rules_path = (ROOT / rules_rel).resolve()

    taxonomy = load_yaml(taxonomy_path)
    rules = load_yaml(rules_path)

    return defaults, taxonomy, rules


def build_effective_config(
    defaults: Dict[str, Any],
    taxonomy: Dict[str, Any],
    rules: Dict[str, Any],
    cli_overrides: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Construct the effective config dict used for fingerprint & snapshot."""

    return {
        "defaults": defaults,
        "taxonomy": taxonomy,
        "rules": rules,
        "thresholds": defaults.get("thresholds", {}),
        "cli_overrides": cli_overrides or {},
    }


def compute_config_fingerprint(
    effective_config: Dict[str, Any],
) -> Tuple[str, str]:
    """Return (fingerprint_sha256, canonical_json_str)."""

    canonical = canonical_json(effective_config)
    return sha256_text(canonical), canonical


def get_git_commit(root: Path | None = None) -> str | None:
    """Best-effort fetch of current git commit hash."""

    try:
        cwd = str(root or ROOT)
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=cwd, stderr=subprocess.DEVNULL, text=True
        ).strip()
        return out or None
    except Exception:
        return None

