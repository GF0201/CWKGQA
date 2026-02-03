"""Schema definition for the generic `domain_main` dataset.

The goal is to keep the schema minimal but explicit and easy to validate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class DomainMainSample:
    """Minimal schema for a QA-style sample."""

    qid: str
    question: str
    answers: List[Any] = field(default_factory=list)
    evidence: Any | None = None

    @staticmethod
    def from_dict(obj: Dict[str, Any]) -> "DomainMainSample":
        """Create a `DomainMainSample` from a raw dict, with basic coercion."""
        ok, msg = validate_sample_dict(obj)
        if not ok:
            raise ValueError(f"invalid DomainMainSample: {msg}")
        return DomainMainSample(
            qid=str(obj["qid"]),
            question=str(obj["question"]),
            answers=list(obj.get("answers", [])),
            evidence=obj.get("evidence"),
        )


def validate_sample_dict(obj: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate that a raw dict follows the DomainMainSample schema.

    Returns
    -------
    (ok, message)
        ok=True  -> sample is valid
        ok=False -> message describes the first validation error encountered
    """
    if not isinstance(obj, dict):
        return False, "sample must be a dict"

    required = ("qid", "question", "answers")
    for key in required:
        if key not in obj:
            return False, f"missing required field: {key}"

    if not isinstance(obj["qid"], (str, int)):
        return False, "qid must be str or int"
    if not isinstance(obj["question"], str):
        return False, "question must be str"
    if not isinstance(obj["answers"], list):
        return False, "answers must be a list"

    # evidence is optional, type left flexible for now
    return True, "ok"

