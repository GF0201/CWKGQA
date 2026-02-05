#!/usr/bin/env python3
"""Compute SHA256 fingerprint of intent_workspace default config.

- 读取 intent_workspace/configs/intent_experiment_defaults.yaml +
        intent_workspace/configs/intent_taxonomy.yaml +
        intent_workspace/configs/intent_rules.yaml
- 构造统一配置字典并转为 canonical JSON
- 计算 SHA256 指纹并写入 intent_workspace/artifacts/intent_default_config_fingerprint.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _canonical_json(obj: dict) -> str:
    """Canonical JSON with sorted keys for deterministic fingerprint."""

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def main() -> int:
    try:
        import yaml
    except ImportError:
        print("PyYAML required: pip install pyyaml", file=sys.stderr)
        return 1

    defaults_path = ROOT / "intent_workspace" / "configs" / "intent_experiment_defaults.yaml"
    taxonomy_path = ROOT / "intent_workspace" / "configs" / "intent_taxonomy.yaml"
    rules_path = ROOT / "intent_workspace" / "configs" / "intent_rules.yaml"

    for p in (defaults_path, taxonomy_path, rules_path):
        if not p.exists():
            print(f"Config not found: {p}", file=sys.stderr)
            return 1

    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8")) or {}
    taxonomy = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8")) or {}
    rules = yaml.safe_load(rules_path.read_text(encoding="utf-8")) or {}

    cfg = {
        "defaults": defaults,
        "taxonomy": taxonomy,
        "rules": rules,
    }
    canonical = _canonical_json(cfg)
    fingerprint_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    out = {
        "fingerprint_sha256": fingerprint_sha256,
        "config_paths": {
            "defaults": str(defaults_path),
            "taxonomy": str(taxonomy_path),
            "rules": str(rules_path),
        },
    }

    artifacts_dir = ROOT / "intent_workspace" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifacts_dir / "intent_default_config_fingerprint.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"fingerprint_sha256: {fingerprint_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

