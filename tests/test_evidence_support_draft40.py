"""TASK 18.2: Case-based regression test for draft_40 support.

draft_40: raw_answer="Individual/Group", evidence_line_ids=[1],
retrieved_triples[0].object contains "Individual/Group"
=> coverage==1.0, support_ge_0_5==True, violation==False
"""
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framework.evidence_support import compute_support  # type: ignore


def test_draft40_support_coverage():
    """draft_40: raw_answer 与 evidence 指向 triple 一致时，support 必须是 1.0。"""
    raw_answer = "Individual/Group"
    evidence_line_ids = [1]
    retrieved_triples = [
        {"subject": "I/G位", "predicate": "表示", "object": "Individual/Group"},
        {"subject": "MAC地址", "predicate": "第一字节的最低有效位为", "object": "I/G位"},
    ]
    result = compute_support(
        raw_answer,
        evidence_line_ids,
        retrieved_triples,
        key_tokens_k=5,
    )
    assert result["coverage"] == 1.0, f"expected coverage=1.0, got {result['coverage']}"
    assert result["support_ge_0_5"] is True
    assert result["covered_tokens"], "key tokens should be covered"
    violation = result["coverage"] is None or result["coverage"] < 0.5
    assert not violation, "violation must be False when coverage==1.0"
