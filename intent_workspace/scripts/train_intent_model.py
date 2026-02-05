#!/usr/bin/env python3
"""Train a simple multi-label intent classifier (TF-IDF + LogisticRegression OVR).

Inputs (expected, but optional):
    intent_workspace/data/intent_labels_gold.jsonl
    intent_workspace/data/intent_labels_silver.jsonl

Each line should at least contain:
    {
      "id": str,
      "question": str,
      "labels": ["FACTOID", "LIST", ...]
    }

Outputs:
    intent_workspace/artifacts/intent_vectorizer.pkl
    intent_workspace/artifacts/intent_model.pkl
    intent_workspace/artifacts/intent_training_manifest.json

This script is optional; if scikit-learn is not installed or no data files
are found, it will print an informative error and exit non-zero.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from intent_workspace.src.utils import ROOT  # type: ignore


DATA_DIR = ROOT / "intent_workspace" / "data"
ARTIFACTS_DIR = ROOT / "intent_workspace" / "artifacts"


def _sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _collect_training_data() -> Tuple[List[str], List[List[str]], Dict[str, str]]:
    texts: List[str] = []
    label_lists: List[List[str]] = []
    data_hashes: Dict[str, str] = {}

    if not DATA_DIR.exists():
        print(f"Data dir not found: {DATA_DIR}", file=sys.stderr)
        return texts, label_lists, data_hashes

    for name in ("intent_labels_gold.jsonl", "intent_labels_silver.jsonl"):
        path = DATA_DIR / name
        if not path.exists():
            continue
        rows = _load_jsonl(path)
        for r in rows:
            q = r.get("question") or ""
            labels = r.get("labels") or []
            if not q or not labels:
                continue
            texts.append(str(q))
            label_lists.append([str(l) for l in labels])
        data_hashes[name] = _sha256_file(path)

    return texts, label_lists, data_hashes


def _binarize_labels(label_lists: List[List[str]]) -> Tuple[List[str], List[List[int]]]:
    all_labels: List[str] = sorted({l for labels in label_lists for l in labels})
    label_to_idx = {l: i for i, l in enumerate(all_labels)}
    Y: List[List[int]] = []
    for labels in label_lists:
        row = [0] * len(all_labels)
        for l in labels:
            if l in label_to_idx:
                row[label_to_idx[l]] = 1
        Y.append(row)
    return all_labels, Y


@dataclass
class TrainingManifest:
    label_order: List[str]
    n_samples: int
    data_hashes: Dict[str, str]
    sklearn_version: str
    random_state: int


def main() -> int:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        from sklearn.linear_model import LogisticRegression  # type: ignore
        from sklearn.multiclass import OneVsRestClassifier  # type: ignore
        import sklearn  # type: ignore
    except Exception as e:
        print(
            f"scikit-learn is required for training intent model: {e}. "
            "Install with `pip install scikit-learn`.",
            file=sys.stderr,
        )
        return 1

    texts, label_lists, data_hashes = _collect_training_data()
    if not texts:
        print(
            f"No training data found under {DATA_DIR} (expected intent_labels_*.jsonl).",
            file=sys.stderr,
        )
        return 1

    label_order, Y = _binarize_labels(label_lists)
    if not label_order:
        print("No labels found in training data.", file=sys.stderr)
        return 1

    random_state = 42
    vectorizer = TfidfVectorizer(max_features=20000, ngram_range=(1, 2))
    X = vectorizer.fit_transform(texts)

    base_clf = LogisticRegression(
        max_iter=1000,
        solver="liblinear",
        random_state=random_state,
    )
    clf = OneVsRestClassifier(base_clf)
    clf.fit(X, Y)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    import joblib  # type: ignore

    vec_path = ARTIFACTS_DIR / "intent_vectorizer.pkl"
    model_path = ARTIFACTS_DIR / "intent_model.pkl"
    joblib.dump(vectorizer, vec_path)
    joblib.dump(clf, model_path)

    manifest = TrainingManifest(
        label_order=label_order,
        n_samples=len(texts),
        data_hashes=data_hashes,
        sklearn_version=getattr(sklearn, "__version__", "unknown"),
        random_state=random_state,
    )
    manifest_path = ARTIFACTS_DIR / "intent_training_manifest.json"
    manifest_path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote model to {model_path} and vectorizer to {vec_path}")
    print(f"Wrote manifest to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

