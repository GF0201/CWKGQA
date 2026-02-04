#!/usr/bin/env python3
"""Baseline QA experiment runner over domain_main KG, with local model support.

Features:
- Simple retrieval over triples.jsonl
- Local model generation via OpenAI-compatible API (e.g. Ollama / vLLM)
- SQuAD-style EM / F1 evaluation and per-sample logging
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Iterable, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framework.utils import (  # type: ignore
    ROOT as FW_ROOT,
    resolve,
    ensure_dir,
    load_jsonl,
    save_jsonl,
    RUNS_DIR,
)
from framework.eval import evaluate_prediction  # type: ignore
from core import set_seed, DualLogger, write_repro_manifest  # type: ignore


# Defaults suitable for local Ollama
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "deepseek-r1:7b"
DEFAULT_API_KEY = "ollama"


@dataclass
class Triple:
    subject: str
    predicate: str
    obj: str


def _normalize_text(s: str | None) -> str:
    return (s or "").strip()


def load_kg_triples(path: Path) -> List[Triple]:
    rows = load_jsonl(path)
    triples: List[Triple] = []
    for r in rows:
        s = _normalize_text(r.get("subject") or r.get("head"))
        p = _normalize_text(r.get("predicate") or r.get("connect"))
        o = _normalize_text(r.get("object") or r.get("tail"))
        if not (s or p or o):
            continue
        triples.append(Triple(s, p, o))
    return triples


def retrieve_triples(question: str, triples: List[Triple], top_k: int = 10) -> List[Triple]:
    """Very simple lexical retriever: subject/object substring match in question."""
    q = question
    scored: List[Tuple[int, int]] = []  # (score, idx)
    for i, t in enumerate(triples):
        score = 0
        if t.subject and t.subject in q:
            score += len(t.subject)
        if t.obj and t.obj in q:
            score += len(t.obj)
        if score > 0:
            scored.append((score, i))
    scored.sort(reverse=True)
    indices = [idx for _, idx in scored[:top_k]]
    return [triples[i] for i in indices]


PROMPT_CONTRACT_VERSION = "short_answer_v1"
GENERATOR_PARSE_VERSION = "v1_content_or_text"
RETRY_MAX = 3


def format_context_structured(triples: Iterable[Triple]) -> str:
    """结构化 triple 格式：每条单行，显式标注 subject/predicate/object。"""
    lines = []
    for t in triples:
        lines.append(f"subject: {t.subject}\tpredicate: {t.predicate}\tobject: {t.obj}")
    return "\n".join(lines) if lines else "(无检索结果)"


def format_context(triples: Iterable[Triple]) -> str:
    return format_context_structured(triples)


def _extract_content(resp: Any) -> tuple[str, str]:
    """从 OpenAI 兼容返回中提取文本。返回 (text, status)。"""
    try:
        if not resp.choices:
            return "", "parse_fail"
        c0 = resp.choices[0]
        text = None
        if hasattr(c0, "message") and c0.message:
            text = getattr(c0.message, "content", None)
        if (text is None or text == "") and hasattr(c0, "text"):
            text = c0.text
        out = (text or "").strip()
        if not out:
            return "", "empty"
        return out, "success"
    except Exception:
        return "", "parse_fail"


def generate_answer_local(
    question: str,
    context: str,
    base_url: str,
    model: str,
    api_key: str,
    mock: bool,
) -> tuple[str, str, int, str]:
    """返回 (prediction, generator_status, attempts, last_error_message)。"""
    if mock:
        return "（Mock 模式：此答案仅用于测试流程连通性。）", "success", 1, ""

    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        raise RuntimeError("导入 openai 失败，请先安装依赖：pip install openai") from e

    client = OpenAI(base_url=base_url, api_key=api_key)
    system_prompt = (
        "你是一个知识库问答助手。输出契约：只输出最终答案，不要解释。"
        "若无法从给定的 triples 得到答案，请输出 UNKNOWN。"
    )
    user_prompt = (
        "[Triples]\n以下是检索到的三元组（每行格式：subject / predicate / object）：\n"
        f"{context}\n\n"
        "[Task]\n请仅根据上述 triples 回答下面的问题。只输出最终答案，不要解释。"
        "若 triples 中无法得到答案，输出 UNKNOWN。\n"
        f"问题：{question}\n"
        "答案："
    )

    last_err = ""
    fail_reason = "empty"
    for attempt in range(1, RETRY_MAX + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=128,
            )
            text, status = _extract_content(resp)
            if status == "success":
                return text, "success", attempt, ""
            if status == "empty":
                last_err = "empty_output"
                fail_reason = "empty"
                continue
            last_err = "parse_fail"
            fail_reason = "parse_fail"
        except Exception as e:
            msg = str(e)
            last_err = msg[:200]
            if "Connection refused" in msg or "Failed to establish" in msg:
                raise RuntimeError(
                    f"无法连接到本地模型服务（base_url={base_url}）。"
                    "请确认 Ollama/vLLM 是否已启动。"
                ) from e
            if "timeout" in msg.lower() or "timed out" in msg.lower():
                fail_reason = "timeout"
                continue
            if "5" in msg or "500" in msg or "502" in msg or "503" in msg:
                fail_reason = "http_fail"
                continue
            raise

    return "", fail_reason, RETRY_MAX, last_err or "max_retries"


def run_experiment(args: argparse.Namespace) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    test_path = resolve(args.test_data)
    kg_path = resolve(args.kg_data)

    test_samples = load_jsonl(test_path)
    triples = load_kg_triples(kg_path)

    if not test_samples:
        raise RuntimeError(f"Test data is empty: {test_path}")
    if not triples:
        raise RuntimeError(f"KG triples is empty: {kg_path}")

    per_sample_results: List[Dict[str, Any]] = []
    total_em = 0.0
    total_f1 = 0.0

    for ex in test_samples:
        qid = ex.get("id") or ex.get("qid") or ""
        question = ex.get("question") or ""
        gold_answers = ex.get("gold_answers") or []

        retrieved = retrieve_triples(question, triples, top_k=10)
        context_str = format_context(retrieved)

        if args.mock:
            pred = (gold_answers[0] if gold_answers else "（Mock 答案）").strip()
            gen_status, attempts = "success", 1
            last_err = ""
        else:
            pred, gen_status, attempts, last_err = generate_answer_local(
                question=question,
                context=context_str,
                base_url=args.base_url,
                model=args.model,
                api_key=args.api_key,
                mock=False,
            )

        em, f1 = evaluate_prediction(pred, gold_answers)
        total_em += em
        total_f1 += f1

        per_sample_results.append(
            {
                "id": qid,
                "question": question,
                "prediction": pred,
                "gold_answers": gold_answers,
                "em": em,
                "f1": f1,
                "generator_status": gen_status,
                "attempts": attempts,
                "retrieved_triples": [
                    {"subject": t.subject, "predicate": t.predicate, "object": t.obj} for t in retrieved
                ],
            }
        )

    n = len(per_sample_results)
    avg_em = total_em / n if n else 0.0
    avg_f1 = total_f1 / n if n else 0.0

    metrics = {
        "total": {
            "n": n,
            "EM": avg_em,
            "F1": avg_f1,
        },
        # 为了兼容可能的两层指标结构，这里复制一份
        "executable_or_answerable": {
            "n": n,
            "EM": avg_em,
            "F1": avg_f1,
        },
    }
    return metrics, per_sample_results


def main() -> int:
    parser = argparse.ArgumentParser(description="Baseline QA experiment over domain_main KG")
    parser.add_argument(
        "--test_data",
        type=str,
        default="datasets/domain_main_qa/test.jsonl",
        help="QA test set (JSONL)",
    )
    parser.add_argument(
        "--kg_data",
        type=str,
        default="datasets/domain_main_kg/processed/merged/triples.jsonl",
        help="KG triples (JSONL)",
    )
    parser.add_argument(
        "--base_url",
        type=str,
        default=DEFAULT_BASE_URL,
        help="OpenAI-compatible base URL (e.g. Ollama/vLLM endpoint)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help="Model name served at the OpenAI-compatible endpoint",
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default=DEFAULT_API_KEY,
        help="API key (for local models usually any non-empty string)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock answers (no model call) to test pipeline connectivity",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output_id",
        type=str,
        default=None,
        help="Run id under runs/; default: exp_baseline_<timestamp>",
    )
    args = parser.parse_args()

    set_seed(args.seed)

    exp_id = args.output_id or f"exp_baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = RUNS_DIR / exp_id
    artifacts_dir = ensure_dir(run_dir / "artifacts")

    logger = DualLogger(run_dir, "run.log")
    start_time = datetime.now().isoformat()
    logger.log(f"argv: {' '.join(sys.argv)}")
    logger.log(f"Baseline experiment started (run_id={exp_id})")

    try:
        metrics, per_sample = run_experiment(args)
    except RuntimeError as e:
        logger.log(f"FATAL: {e}")
        print(str(e), file=sys.stderr)
        logger.close()
        return 1
    except Exception as e:  # pragma: no cover - defensive
        logger.log(f"UNEXPECTED ERROR: {e!r}")
        print(f"Unexpected error: {e!r}", file=sys.stderr)
        logger.close()
        return 1

    # Save metrics and per-sample results
    import core.metrics as core_metrics  # type: ignore

    metrics_path = run_dir / "metrics.json"
    audit = {
        "eval_tokenizer": "mixed_zh_char_en_word_v1",
        "generator_parse_version": GENERATOR_PARSE_VERSION,
        "retry_policy": f"max_attempts={RETRY_MAX}",
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
    }
    metrics.setdefault("audit", {}).update(audit)
    core_metrics.save_metrics(metrics, metrics_path)
    save_jsonl(per_sample, artifacts_dir / "per_sample_results.jsonl")

    gen_status_rows = [
        {"id": s.get("id"), "generator_status": s.get("generator_status", ""), "attempts": s.get("attempts", 1)}
        for s in per_sample
    ]
    save_jsonl(gen_status_rows, artifacts_dir / "per_sample_generator_status.jsonl")

    prompt_template = (
        "=== System ===\n"
        "你是一个知识库问答助手。输出契约：只输出最终答案，不要解释。"
        "若无法从给定的 triples 得到答案，请输出 UNKNOWN。\n\n"
        "=== User (结构) ===\n"
        "[Triples]\n每行格式: subject: X\tpredicate: Y\tobject: Z\n"
        "[Task]\n请仅根据上述 triples 回答。只输出最终答案，不要解释。无法得到答案则输出 UNKNOWN。\n"
        f"prompt_contract_version={PROMPT_CONTRACT_VERSION}"
    )
    (artifacts_dir / "prompt_template_used.txt").write_text(prompt_template, encoding="utf-8")

    # Repro manifest
    end_time = datetime.now().isoformat()
    inputs = [resolve(args.test_data), resolve(args.kg_data)]
    manifest = write_repro_manifest(
        run_dir,
        run_id=exp_id,
        start_time=start_time,
        end_time=end_time,
        command_argv=sys.argv,
        seed=args.seed,
        inputs=inputs,
        config_dict={},
        args={
            "test_data": str(resolve(args.test_data)),
            "kg_data": str(resolve(args.kg_data)),
            "base_url": args.base_url,
            "model": args.model,
            "mock": args.mock,
        },
        warnings=[],
        old_dir=None,
        data_file=resolve(args.test_data),
        extra_fields={"phase": "eval", "runner_name": "run_exp_baseline"},
    )
    logger.log("Saved repro_manifest.json")
    logger.log(
        f"Inputs hashed: {len(manifest.get('input_files_sha256', {}))}; "
        f"first_keys={list(manifest.get('input_files_sha256', {}).keys())[:3]}"
    )

    logger.log(
        f"Baseline finished: n={metrics['total']['n']}, "
        f"EM={metrics['total']['EM']:.3f}, F1={metrics['total']['F1']:.3f}"
    )
    logger.close()
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

