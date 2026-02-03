"""Dataset-level validation utilities for `domain_main`."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from core.io import load_jsonl, save_jsonl
from .schema import validate_sample_dict


def validate_dataset(file_path: Path | str) -> Tuple[int, int, Path | None]:
    """Validate a dataset file against the DomainMainSample schema.

    Parameters
    ----------
    file_path:
        Path to a JSONL file where each line is a sample dict.

    Returns
    -------
    (ok_count, bad_count, bad_examples_path)
        bad_examples_path is a JSONL file containing invalid samples
        with an added `_error` field describing the reason, or None
        if there are no invalid samples.
    """
    path = Path(file_path)
    data = load_jsonl(path)

    ok_count = 0
    bad = []
    for obj in data:
        ok, msg = validate_sample_dict(obj)
        if ok:
            ok_count += 1
        else:
            bad.append({**obj, "_error": msg})

    bad_count = len(bad)
    bad_examples_path: Path | None
    if bad:
        bad_examples_path = path.with_suffix(path.suffix + ".bad.jsonl")
        save_jsonl(bad, bad_examples_path)
    else:
        bad_examples_path = None

    return ok_count, bad_count, bad_examples_path

