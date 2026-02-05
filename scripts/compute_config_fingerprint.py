#!/usr/bin/env python3
"""Compute SHA256 fingerprint of default config for TASK 16."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _canonical_json(obj: dict) -> str:
    """Canonical JSON with sorted keys for deterministic fingerprint."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def main() -> int:
    config_path = ROOT / "configs" / "default_real_bm25_k10_evidence_guardrail_v2.yaml"
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1

    try:
        import yaml

        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except ImportError:
        print("PyYAML required: pip install pyyaml", file=sys.stderr)
        return 1

    if cfg is None:
        cfg = {}
    canonical = _canonical_json(cfg)
    fingerprint_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    key_fields = {
        "retriever_type": cfg.get("retriever", {}).get("type", ""),
        "retriever_topk": cfg.get("retriever", {}).get("topk"),
        "contract_type": cfg.get("contract", {}).get("type", ""),
        "guardrail_version": cfg.get("guardrail", {}).get("version", ""),
        "enforcement_policy": cfg.get("guardrail", {}).get("enforcement_policy", ""),
        "support_semantics_version": cfg.get("support", {}).get("semantics_version", ""),
        "generator_model": cfg.get("generator", {}).get("model", ""),
        "generator_seed": cfg.get("generator", {}).get("seed"),
    }

    out = {
        "fingerprint_sha256": fingerprint_sha256,
        "key_fields_summary": key_fields,
        "config_path": str(config_path),
    }

    artifacts_dir = ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifacts_dir / "default_config_fingerprint.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"fingerprint_sha256: {fingerprint_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
