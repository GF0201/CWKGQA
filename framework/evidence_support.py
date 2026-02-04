from __future__ import annotations

"""Parsing and evidence-support utilities for Answer+Evidence contracts.

Design:
- parse_contract(text) -> normalized raw_answer + evidence_line_ids + parse flags
- compute_support(raw_answer, evidence_line_ids, retrieved_triples, key_tokens_k)
  -> coverage stats based on raw_answer ONLY (final_answer/enforcement 不参与)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple
import hashlib

from .eval import normalize_answer, mixed_segmentation  # type: ignore


SUPPORT_SEMANTICS_VERSION = "raw_answer_only_v1"


@dataclass
class ParsedContract:
    raw_answer: str
    evidence_line_ids: List[int]
    has_answer_line: bool
    has_evidence_line: bool
    evidence_empty: bool
    evidence_out_of_range: bool
    evidence_has_duplicate: bool


def parse_contract(text: str, retrieved_k: int | None = None) -> ParsedContract:
    """Parse two-line contract text into raw_answer and evidence ids.

    - ANSWER: <...>
    - EVIDENCE: <1,2,...>
    """
    raw = (text or "").strip()
    if not raw:
        return ParsedContract(
            raw_answer="",
            evidence_line_ids=[],
            has_answer_line=False,
            has_evidence_line=False,
            evidence_empty=True,
            evidence_out_of_range=False,
            evidence_has_duplicate=False,
        )

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    answer = raw
    evidence_ids: List[int] = []
    has_answer_line = False
    has_evidence_line = False
    evidence_empty = False
    evidence_out_of_range = False
    evidence_has_duplicate = False

    # ANSWER 行：只取内容部分进入后续 eval/support
    for ln in lines:
        upper = ln.upper()
        if upper.startswith("ANSWER:"):
            has_answer_line = True
            answer = ln[len("ANSWER:") :].strip()
            break

    # EVIDENCE 行：解析逗号分隔的行号
    seen_raw: List[int] = []
    for ln in lines:
        upper = ln.upper()
        if upper.startswith("EVIDENCE:"):
            has_evidence_line = True
            payload = ln[len("EVIDENCE:") :].strip()
            if not payload:
                evidence_empty = True
                break
            raw_tokens = [t.strip() for t in payload.replace("，", ",").split(",") if t.strip()]
            for tok in raw_tokens:
                try:
                    idx = int(tok)
                except ValueError:
                    # 非整数 token 直接忽略
                    continue
                seen_raw.append(idx)
                if retrieved_k is not None and (idx < 1 or idx > max(retrieved_k, 0)):
                    evidence_out_of_range = True
                    continue
                evidence_ids.append(idx)
            if len(seen_raw) != len(set(seen_raw)):
                evidence_has_duplicate = True
            break

    evidence_ids = sorted(set(evidence_ids))
    return ParsedContract(
        raw_answer=answer,
        evidence_line_ids=evidence_ids,
        has_answer_line=has_answer_line,
        has_evidence_line=has_evidence_line,
        evidence_empty=evidence_empty,
        evidence_out_of_range=evidence_out_of_range,
        evidence_has_duplicate=evidence_has_duplicate,
    )


def compute_support(
    raw_answer: str,
    evidence_line_ids: List[int],
    retrieved_triples: List[Dict[str, Any]],
    key_tokens_k: int = 5,
) -> Dict[str, Any]:
    """Compute evidence support for a single sample based on raw_answer.

    Returns a dict with:
    - coverage: float or None
    - support_ge_0_5: bool
    - key_tokens: List[str]
    - covered_tokens / missing_tokens: List[str]
    """
    if not raw_answer or not evidence_line_ids or not retrieved_triples:
        return {
            "coverage": None,
            "support_ge_0_5": False,
            "key_tokens": [],
            "covered_tokens": [],
            "missing_tokens": [],
        }

    norm_answer = normalize_answer(raw_answer)
    ans_tokens = mixed_segmentation(norm_answer)
    key_tokens = ans_tokens[:key_tokens_k]
    if not key_tokens:
        return {
            "coverage": None,
            "support_ge_0_5": False,
            "key_tokens": [],
            "covered_tokens": [],
            "missing_tokens": [],
        }

    ctx_parts: List[str] = []
    for idx in evidence_line_ids:
        j = idx - 1
        if 0 <= j < len(retrieved_triples):
            t = retrieved_triples[j]
            ctx_parts.append(
                f"{t.get('subject','')} {t.get('predicate','')} {t.get('object','')}"
            )

    norm_ctx = normalize_answer(" ".join(ctx_parts)) if ctx_parts else ""
    if not norm_ctx:
        covered: List[str] = []
        missing = key_tokens
        coverage = 0.0
    else:
        # 语义口径：关键 token 作为子串是否出现在被引用 triples 文本中
        covered = [t for t in key_tokens if t and t in norm_ctx]
        missing = [t for t in key_tokens if t and t not in norm_ctx]
        coverage = len(covered) / len(key_tokens) if key_tokens else 0.0

    return {
        "coverage": coverage,
        "support_ge_0_5": coverage >= 0.5,
        "key_tokens": key_tokens,
        "covered_tokens": covered,
        "missing_tokens": missing,
    }


def compute_support_summary(
    samples: List[Dict[str, Any]],
    key_tokens_k: int = 5,
) -> Dict[str, Any]:
    """Aggregate evidence support over a list of per-sample rows.

    Each row is expected to have:
    - raw_answer (or raw_prediction/prediction 作为回退)
    - evidence_line_ids
    - retrieved_triples
    """
    coverages: List[float] = []
    failure_ids: List[str] = []

    for s in samples:
        raw_answer = (s.get("raw_answer") or "").strip()
        if not raw_answer:
            # 兼容旧字段：从 raw_prediction / prediction 中解析
            raw_pred = (s.get("raw_prediction") or s.get("prediction") or "").strip()
            parsed = parse_contract(raw_pred, retrieved_k=len(s.get("retrieved_triples") or []))
            raw_answer = parsed.raw_answer
            s.setdefault("evidence_line_ids", parsed.evidence_line_ids)

        evidence_ids: List[int] = s.get("evidence_line_ids") or []
        retrieved = s.get("retrieved_triples") or []
        support = compute_support(raw_answer, evidence_ids, retrieved, key_tokens_k=key_tokens_k)
        cov = support.get("coverage")
        if cov is None:
            continue
        coverages.append(cov)
        if cov < 0.5:
            failure_ids.append(str(s.get("id", "")))

    n = len(coverages)
    if n == 0:
        return {
            "n": 0,
            "key_tokens_k": key_tokens_k,
            "coverage_mean": 0.0,
            "coverage_median": 0.0,
            "support_rate_ge_0_5": 0.0,
            "failure_case_ids": [],
        }

    srt = sorted(coverages)
    median = srt[len(srt) // 2]
    mean_cov = sum(coverages) / n
    support_rate = sum(1 for c in coverages if c >= 0.5) / n
    return {
        "n": n,
        "key_tokens_k": key_tokens_k,
        "coverage_mean": mean_cov,
        "coverage_median": median,
        "support_rate_ge_0_5": support_rate,
        "failure_case_ids": failure_ids,
    }


def get_module_sha256() -> str:
    """Return sha256 fingerprint of this module file for audit."""
    try:
        path = Path(__file__).resolve()
        data = path.read_bytes()
        return hashlib.sha256(data).hexdigest()
    except Exception:
        return ""

