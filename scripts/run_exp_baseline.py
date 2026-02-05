#!/usr/bin/env python3
"""Baseline QA experiment runner over domain_main KG, with local model support.

Features:
- Simple retrieval over triples.jsonl
- Local model generation via OpenAI-compatible API (e.g. Ollama / vLLM)
- SQuAD-style EM / F1 evaluation and per-sample logging
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Iterable, Tuple

ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = ROOT / "configs"
DEFAULT_CONFIG_PATH = CONFIGS_DIR / "default_real_bm25_k10_evidence_guardrail_v2.yaml"
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
from framework.eval import (  # type: ignore
    evaluate_prediction,
    normalize_answer,
    mixed_segmentation,
)
from core import set_seed, DualLogger, write_repro_manifest  # type: ignore
from src.intent.intent_engine import IntentEngine  # type: ignore


# Defaults suitable for remote DeepSeek API (can be overridden by env)
DEFAULT_BASE_URL = os.getenv("MKEAI_BASE_URL", "https://tb.api.mkeai.com/v1")
DEFAULT_MODEL = os.getenv("MKEAI_MODEL", "deepseek-v3.2")


def _resolve_api_key_and_source() -> tuple[str, str]:
    """Resolve API key from env. Priority: MKEAI_API_KEY > OPENAI_API_KEY.
    Returns (api_key, source_var_name). Records which env var was used (not the value)."""
    mke = os.getenv("MKEAI_API_KEY", "").strip()
    if mke:
        return mke, "MKEAI_API_KEY"
    oai = os.getenv("OPENAI_API_KEY", "").strip()
    if oai:
        return oai, "OPENAI_API_KEY"
    return "", ""


_API_KEY, _API_KEY_SOURCE = _resolve_api_key_and_source()
DEFAULT_API_KEY = _API_KEY


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


def retrieve_triples(
    question: str,
    triples: List[Triple],
    top_k: int = 10,
    retriever_type: str = "simple",
) -> List[Triple]:
    """Very simple lexical retriever with an optional BM25-like variant."""
    q = question
    scored: List[Tuple[float, int]] = []  # (score, idx)

    if retriever_type == "bm25":
        # Extremely simple BM25-ish scoring over concatenated triple text.
        import math

        docs: List[List[str]] = []
        for t in triples:
            text = f"{t.subject} {t.predicate} {t.obj}".strip()
            tokens = text.split()
            docs.append(tokens)

        # Query tokens
        q_tokens = q.split()
        if not q_tokens:
            return []

        # Document frequencies for BM25-like idf
        df = {}
        for tokens in docs:
            seen = set(tokens)
            for tok in seen:
                df[tok] = df.get(tok, 0) + 1
        n_docs = len(docs)
        idf = {tok: math.log((n_docs - c + 0.5) / (c + 0.5) + 1.0) for tok, c in df.items()}

        k1 = 1.5
        b = 0.75
        avgdl = sum(len(d) for d in docs) / n_docs if n_docs else 0.0

        for i, tokens in enumerate(docs):
            score = 0.0
            if not tokens:
                continue
            dl = len(tokens)
            tf = {}
            for tok in tokens:
                tf[tok] = tf.get(tok, 0) + 1
            for qt in q_tokens:
                if qt not in tf or qt not in idf:
                    continue
                freq = tf[qt]
                denom = freq + k1 * (1 - b + b * dl / avgdl) if avgdl > 0 else freq + k1
                score += idf[qt] * (freq * (k1 + 1) / denom)
            if score > 0:
                scored.append((score, i))
    else:
        # simple lexical: subject/object substring match in question
        for i, t in enumerate(triples):
            score = 0.0
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
PROMPT_CONTRACT_VERSION_ANSWER_EVIDENCE = "short_answer_with_evidence_v1"
PROMPT_CONTRACT_VERSION_GUARDRAIL = "short_answer_guardrail_answerable_only_v1"
PROMPT_CONTRACT_VERSION_ANSWER_EVIDENCE_GUARDRAIL_V2 = "short_answer_with_evidence_guardrail_v2"
GENERATOR_PARSE_VERSION = "v1_content_or_text"
RETRY_MAX = 3
GEN_TEMPERATURE = 0.1
GEN_TOP_P = 1.0
GEN_MAX_TOKENS = 128
GEN_SEED = 42


def format_context_structured(triples: Iterable[Triple]) -> str:
    """结构化 triple 格式：每条单行，显式标注 subject/predicate/object。"""
    lines = []
    for t in triples:
        lines.append(f"subject: {t.subject}\tpredicate: {t.predicate}\tobject: {t.obj}")
    return "\n".join(lines) if lines else "(无检索结果)"


def format_context(triples: Iterable[Triple]) -> str:
    return format_context_structured(triples)


def format_context_with_ids(triples: Iterable[Triple]) -> str:
    """在结构化 triple 基础上增加 1‑based 行号，便于模型引用 evidence 行。"""
    lines = []
    for idx, t in enumerate(triples, start=1):
        lines.append(
            f"[{idx}] subject: {t.subject}\tpredicate: {t.predicate}\tobject: {t.obj}"
        )
    return "\n".join(lines) if lines else "(无检索结果)"


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


def _probe_endpoint(base_url: str, model: str, api_key: str) -> tuple[bool, str]:
    """轻量探活：在正式运行前验证生成端是否可用。确保返回 non-empty content；失败则 fail-fast。"""
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        return False, f"导入 openai 失败: {e}"

    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "health check"},
                {"role": "user", "content": "ping"},
            ],
            temperature=0.0,
            max_tokens=16,
        )
        if not hasattr(resp, "choices") or not resp.choices:
            return False, "probe 响应中缺少 choices"
        c0 = resp.choices[0]
        text = (getattr(c0.message, "content", None) if hasattr(c0, "message") and c0.message else None) or getattr(c0, "text", None)
        if not (text and str(text).strip()):
            return False, "probe 返回 content 为空"
        return True, ""
    except Exception as e:  # pragma: no cover - 防御性代码
        return False, f"probe 请求失败: {e}"


def generate_answer_local(
    question: str,
    context: str,
    base_url: str,
    model: str,
    api_key: str,
    mock: bool,
    contract_variant: str,
    use_retry_prompt: bool = False,
) -> tuple[str, str, int, str]:
    """返回 (raw_text, generator_status, attempts, last_error_message)。"""
    if mock:
        return "（Mock 模式：此答案仅用于测试流程连通性。）", "success", 1, ""

    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        raise RuntimeError("导入 openai 失败，请先安装依赖：pip install openai") from e

    client = OpenAI(base_url=base_url, api_key=api_key)

    if contract_variant == "answer_plus_evidence":
        system_prompt = (
            "你是一个知识库问答助手。输出契约：严格输出两行，且不要添加多余文本或解释。\n"
            "Line1: ANSWER: <最终答案或 UNKNOWN>\n"
            "Line2: EVIDENCE: <逗号分隔的行号，范围 1..K，对应给定 triples 的行号>\n"
            "不得输出额外前后缀、空行或说明文字。"
        )
        user_prompt = (
            "[Triples]\n以下是检索到的三元组，每行带有方括号中的行号，可以在 EVIDENCE 中引用：\n"
            f"{context}\n\n"
            "[Task]\n请仅根据上述 triples 回答下面的问题，并按严格格式输出两行：\n"
            "Line1 必须以 `ANSWER:` 开头，只填写最终答案或 UNKNOWN；不要解释。\n"
            "Line2 必须以 `EVIDENCE:` 开头，只填写逗号分隔的行号（1..K），表示支撑答案的 triples 行；"
            "若没有合适证据，可以留空但仍需保留该行。\n"
            f"问题：{question}\n"
            "现在输出："
        )
    elif contract_variant == "answer_plus_evidence_guardrail_v2":
        if use_retry_prompt:
            # Policy R retry prompt: 进一步强调 evidence 选择与 ANSWER 从 evidence 拷贝
            system_prompt = (
                "你是一个知识库问答助手。【重试】上次输出不符合要求。输出契约：严格输出两行。\n"
                "Line1: ANSWER: <最终答案或 UNKNOWN>\n"
                "Line2: EVIDENCE: <逗号分隔的行号，范围 1..K>\n"
                "硬性约束：\n"
                "1）你必须重新选择正确的 evidence 行号；\n"
                "2）ANSWER 必须从 evidence 行中拷贝或轻微改写得到；否则必须输出 UNKNOWN；\n"
                "3）禁止编造、禁止引入 EVIDENCE 行之外的内容；\n"
                "4）严格两行，禁止多余文字。"
            )
            user_prompt = (
                "[Triples]\n以下是检索到的三元组，每行带有方括号中的行号：\n"
                f"{context}\n\n"
                "[Task - 重试]\n请重新选择正确的 evidence 行号；"
                "ANSWER 必须从这些 evidence 行中拷贝或轻微改写；否则输出 UNKNOWN。严格两行。\n"
                f"问题：{question}\n"
                "现在输出："
            )
        else:
            system_prompt = (
                "你是一个知识库问答助手。输出契约：严格输出两行，且不要添加多余文本或解释。\n"
                "Line1: ANSWER: <最终答案或 UNKNOWN>\n"
                "Line2: EVIDENCE: <逗号分隔的行号，范围 1..K，对应给定 triples 的行号>\n"
                "硬性约束：\n"
                "1）你必须先从给定 triples 中选择若干行号作为 EVIDENCE；\n"
                "2）ANSWER 只能从这些 EVIDENCE 行中的 subject/object/数值/术语拷贝或轻微改写得到，"
                "不得引入不在 EVIDENCE 行里的新事实；\n"
                "3）如果在任何 EVIDENCE 行中都找不到能支撑答案的内容（包括同义表达），必须输出 UNKNOWN；\n"
                "4）禁止使用给定 triples 之外的常识或背景知识进行补全；\n"
                "5）禁止解释、禁止多行，只能严格输出上述两行。"
            )
            user_prompt = (
                "[Triples]\n以下是检索到的三元组，每行带有方括号中的行号，可以在 EVIDENCE 中引用：\n"
                f"{context}\n\n"
                "[Task]\n请按如下步骤严格操作：\n"
                "1）先在上述 triples 中选择若干最相关的行号，作为支撑答案的 EVIDENCE；\n"
                "2）仅允许从这些 EVIDENCE 行中的 subject/object/数值/术语进行拷贝或轻微改写来构造答案；\n"
                "3）如果在这些 EVIDENCE 中找不到可以支撑答案的内容，必须输出 UNKNOWN；\n"
                "4）禁止使用 triples 之外的常识或背景知识。\n\n"
                "输出格式必须严格为两行：\n"
                "Line1: ANSWER: <最终答案或 UNKNOWN>\n"
                "Line2: EVIDENCE: <逗号分隔的行号>\n"
                "不得输出多余文字、标点或空行。\n"
                f"问题：{question}\n"
                "现在输出："
            )
    elif contract_variant == "guardrail_answerable_only":
        system_prompt = (
            "你是一个知识库问答助手。硬性约束：只能从给定 triples 中提取答案，"
            "绝对禁止编造、不在 triples 中出现的事实。\n"
            "若在 triples 中找不到足够信息，请输出 UNKNOWN。输出契约：只输出最终答案或 UNKNOWN，不要解释。"
        )
        user_prompt = (
            "[Triples]\n以下是检索到的三元组（每行格式：subject / predicate / object）：\n"
            f"{context}\n\n"
            "[Task]\n请仅根据上述 triples 回答下面的问题。\n"
            "如果你无法在 triples 中找到足够的信息来确定答案，必须输出 UNKNOWN，"
            "不得根据常识或背景知识猜测。\n"
            "输出契约：只输出一个简洁的最终答案或 UNKNOWN，不要解释。\n"
            f"问题：{question}\n"
            "答案："
        )
    else:
        # 默认：原始 short_answer_v1 合同，仅输出最终答案或 UNKNOWN
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
                temperature=GEN_TEMPERATURE,
                top_p=GEN_TOP_P,
                max_tokens=GEN_MAX_TOKENS,
                seed=GEN_SEED,
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


def _parse_answer_and_evidence(
    raw_text: str,
    retrieved_k: int,
) -> tuple[str, list[int], Dict[str, Any]]:
    """解析 ANSWER/EVIDENCE 两行格式。

    返回：
    - answer: 供评测使用的 ANSWER 行内容
    - evidence_ids: 解析出的 1‑based evidence 行号列表（去重且按升序）
    - meta: 解析过程的一些标记，用于统计报告
    """
    meta: Dict[str, Any] = {
        "has_evidence_line": False,
        "evidence_empty": False,
        "evidence_out_of_range": False,
        "evidence_has_duplicate": False,
    }
    if not raw_text.strip():
        meta["evidence_empty"] = True
        return "", [], meta

    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    answer = raw_text.strip()
    evidence_ids: list[int] = []

    # 解析 ANSWER 行
    for ln in lines:
        if ln.upper().startswith("ANSWER:"):
            answer = ln[len("ANSWER:") :].strip()
            break

    # 解析 EVIDENCE 行
    for ln in lines:
        if ln.upper().startswith("EVIDENCE:"):
            meta["has_evidence_line"] = True
            payload = ln[len("EVIDENCE:") :].strip()
            if not payload:
                meta["evidence_empty"] = True
                break
            raw_tokens = [t.strip() for t in payload.replace("，", ",").split(",") if t.strip()]
            seen_raw: list[int] = []
            for tok in raw_tokens:
                try:
                    idx = int(tok)
                except ValueError:
                    # 忽略非整数 token
                    continue
                seen_raw.append(idx)
                if idx < 1 or idx > max(retrieved_k, 0):
                    meta["evidence_out_of_range"] = True
                    continue
                evidence_ids.append(idx)
            if len(seen_raw) != len(set(seen_raw)):
                meta["evidence_has_duplicate"] = True
            break

    # 去重并排序合法的 evidence id
    evidence_ids = sorted(set(evidence_ids))
    return answer, evidence_ids, meta


def _load_default_config_and_fingerprint() -> tuple[dict | None, str]:
    """Load default config and return (config_dict, fingerprint_sha256)."""
    if not DEFAULT_CONFIG_PATH.exists():
        return None, ""
    try:
        import yaml  # type: ignore

        cfg = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None, ""
    if cfg is None:
        cfg = {}
    canonical = json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    fp = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return cfg, fp


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    i = int((len(s) - 1) * q)
    return s[min(i, len(s) - 1)]


EVIDENCE_KEY_TOKENS_K = 5


def _compute_single_evidence_support(
    answer: str,
    evidence_ids: list[int],
    retrieved: list[dict],
) -> float | None:
    """计算单个样本的 evidence 支持率；若无法计算则返回 None。

    raw_answer_only_v1 语义：key_tokens 作为子串是否出现在 norm_ctx 中（与 framework/evidence_support 一致）。
    """
    if not evidence_ids:
        return None
    if not answer or not retrieved:
        return None

    norm_answer = normalize_answer(answer)
    ans_tokens = mixed_segmentation(norm_answer)
    key_tokens = ans_tokens[:EVIDENCE_KEY_TOKENS_K]
    if not key_tokens:
        return None

    ctx_parts: list[str] = []
    for idx in evidence_ids:
        j = idx - 1
        if 0 <= j < len(retrieved):
            t = retrieved[j]
            ctx_parts.append(
                f"{t.get('subject','')} {t.get('predicate','')} {t.get('object','')}"
            )
    if not ctx_parts:
        return None

    norm_ctx = normalize_answer(" ".join(ctx_parts))
    if not norm_ctx:
        return None

    # raw_answer_only_v1: 子串匹配，key token 需作为子串出现在 ctx 中
    covered = [t for t in key_tokens if t and t in norm_ctx]
    return len(covered) / len(key_tokens)


def _compute_evidence_support_summary(samples: list[dict]) -> Dict[str, Any]:
    """基于 prediction + evidence_line_ids + retrieved_triples 计算 evidence 支持率诊断。"""
    coverages: list[float] = []
    failure_ids: list[str] = []

    for s in samples:
        evidence_ids: list[int] = s.get("evidence_line_ids") or []
        retrieved = s.get("retrieved_triples") or []
        pred = (s.get("prediction") or "").strip()
        cov = _compute_single_evidence_support(pred, evidence_ids, retrieved)
        if cov is None:
            continue
        coverages.append(cov)
        if cov < 0.5:
            failure_ids.append(str(s.get("id", "")))

    n = len(coverages)
    if n == 0:
        return {
            "n": 0,
            "key_tokens_k": EVIDENCE_KEY_TOKENS_K,
            "coverage_mean": 0.0,
            "coverage_median": 0.0,
            "support_rate_ge_0_5": 0.0,
            "failure_case_ids": [],
        }

    mean_cov = sum(coverages) / n
    med_cov = _quantile(coverages, 0.5)
    support_rate = sum(1 for c in coverages if c >= 0.5) / n
    return {
        "n": n,
        "key_tokens_k": EVIDENCE_KEY_TOKENS_K,
        "coverage_mean": mean_cov,
        "coverage_median": med_cov,
        "support_rate_ge_0_5": support_rate,
        "failure_case_ids": failure_ids,
    }


def run_experiment(
    args: argparse.Namespace,
    log_fn: Any = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """log_fn: optional callback for enforce logs, e.g. logger.log."""
    _log = log_fn if callable(log_fn) else (lambda _: None)
    test_path = resolve(args.test_data)
    kg_path = resolve(args.kg_data)

    test_samples = load_jsonl(test_path)
    triples = load_kg_triples(kg_path)

    # 可选：启用 IntentEngine（Task 18）
    intent_engine: IntentEngine | None = None
    intent_audit: Dict[str, Any] | None = None
    if getattr(args, "intent_mode", "none") != "none":
        intent_engine = IntentEngine()
        intent_audit = intent_engine.get_audit_info()

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

        # --- IntentEngine 预测 ---
        intent_pred: Dict[str, Any] | None = None
        if intent_engine is not None:
            intent_pred = intent_engine.predict(str(question))

        # 默认检索/合同设置（可被 intent 路由覆盖）
        retriever_type_local = args.retriever_type
        top_k_local = args.top_k

        if intent_pred is not None and getattr(args, "intent_mode", "none") in ("rule_v1_route", "rule_v1_clarify"):
            intents = intent_pred.get("intents") or []
            top_label = intents[0]["label"] if intents else None
            is_multi_intent = bool(intent_pred.get("is_multi_intent"))

            # 简化版路由策略：仅调整检索类型与 top_k
            if top_label in ("FACTOID", "LIST", "FILTER"):
                retriever_type_local = "bm25"
                top_k_local = max(top_k_local, 10)
            elif top_label in ("COMPARISON", "PROCEDURE"):
                retriever_type_local = "bm25"
                top_k_local = max(top_k_local, 10)

            if is_multi_intent:
                # 多意图样本：扩大检索范围
                top_k_local = max(top_k_local, args.top_k * 2)

        retrieved = retrieve_triples(
            question,
            triples,
            top_k=top_k_local,
            retriever_type=retriever_type_local,
        )
        if args.contract_variant in ("answer_plus_evidence", "answer_plus_evidence_guardrail_v2"):
            context_str = format_context_with_ids(retrieved)
        else:
            context_str = format_context(retrieved)

        evidence_ids: list[int] = []
        evidence_meta: Dict[str, Any] | None = None
        raw_pred = ""
        raw_answer = ""
        raw_answer_retry: str | None = None
        evidence_line_ids_retry: list[int] | None = None
        evidence_support_retry: float | None = None
        evidence_violation_retry: bool | None = None
        final_answer_after_retry: str | None = None
        retry_attempted: bool = False

        clarify_applied = False
        answer_before_clarify: str | None = None
        if args.mock:
            pred = (gold_answers[0] if gold_answers else "（Mock 答案）").strip()
            gen_status, attempts = "success", 1
            last_err = ""
            raw_pred = pred
            raw_answer = pred
            evidence_support = 1.0
            violation = False
            enforcement_action = "none"
            em, f1 = evaluate_prediction(pred, gold_answers)
        else:
            raw_pred, gen_status, attempts, last_err = generate_answer_local(
                question=question,
                context=context_str,
                base_url=args.base_url,
                model=args.model,
                api_key=args.api_key,
                mock=False,
                contract_variant=args.contract_variant,
            )
            if args.contract_variant in ("answer_plus_evidence", "answer_plus_evidence_guardrail_v2"):
                answer_text, evidence_ids, evidence_meta = _parse_answer_and_evidence(
                    raw_pred,
                    retrieved_k=len(retrieved),
                )
                # 先基于原始 ANSWER 计算 evidence 支持率（support_semantics: raw_answer_only_v1）
                retrieved_dicts = [
                    {"subject": t.subject, "predicate": t.predicate, "object": t.obj} for t in retrieved
                ]
                evidence_support = _compute_single_evidence_support(
                    answer_text,
                    evidence_ids,
                    retrieved_dicts,
                )
                violation = evidence_support is None or evidence_support < 0.5
                enforcement_action = "none"
                pred = answer_text
                raw_answer = answer_text

                policy = (args.enforcement_policy or "").strip()
                if args.contract_variant == "answer_plus_evidence_guardrail_v2":
                    if not policy:
                        policy = "force_unknown_if_support_lt_0.5"
                    if policy == "force_unknown_if_support_lt_0.5":
                        # Policy B: 若 support < 0.5，直接强制 UNKNOWN
                        if violation:
                            enforcement_action = "force_unknown"
                            pred = "UNKNOWN"
                    elif policy == "retry_once_if_support_lt_0.5_else_force_unknown":
                        # Policy R: violation 时先 retry 一次；若 retry 后仍 violation，force UNKNOWN
                        if violation:
                            retry_attempted = True
                            _log(f"[ENFORCE] id={qid} policy=R violation=True -> retry")
                            raw_retry, gen_status_retry, attempts_retry, _ = generate_answer_local(
                                question=question,
                                context=context_str,
                                base_url=args.base_url,
                                model=args.model,
                                api_key=args.api_key,
                                mock=False,
                                contract_variant=args.contract_variant,
                                use_retry_prompt=True,
                            )
                            if gen_status_retry == "success" and raw_retry.strip():
                                ans_retry, evidence_ids_retry, _ = _parse_answer_and_evidence(
                                    raw_retry, retrieved_k=len(retrieved)
                                )
                                support_retry = _compute_single_evidence_support(
                                    ans_retry, evidence_ids_retry, retrieved_dicts
                                )
                                raw_answer_retry = ans_retry
                                evidence_line_ids_retry = evidence_ids_retry
                                evidence_support_retry = support_retry
                                still_violation = support_retry is None or support_retry < 0.5
                                evidence_violation_retry = still_violation
                                if still_violation:
                                    enforcement_action = "retry_then_force_unknown"
                                    pred = "UNKNOWN"
                                    final_answer_after_retry = "UNKNOWN"
                                else:
                                    enforcement_action = "retry_resolved"
                                    pred = ans_retry
                                    final_answer_after_retry = ans_retry
                                _log(f"[ENFORCE] id={qid} retry_result violation={still_violation} action={enforcement_action}")
                            else:
                                evidence_violation_retry = True
                                enforcement_action = "retry_then_force_unknown"
                                pred = "UNKNOWN"
                                final_answer_after_retry = "UNKNOWN"
                                _log(f"[ENFORCE] id={qid} retry_result violation=True action=retry_then_force_unknown (retry_fail)")
                        else:
                            enforcement_action = "none"
                else:
                    violation = False
                    enforcement_action = "none"
                em, f1 = evaluate_prediction(pred, gold_answers)
            else:
                pred = raw_pred
                evidence_support = None
                violation = False
                enforcement_action = "none"
                em, f1 = evaluate_prediction(pred, gold_answers)

        # 澄清模式（离线）：若样本被标记为歧义，则将最终答案强制为 UNKNOWN
        if (
            intent_pred is not None
            and getattr(args, "intent_mode", "none") == "rule_v1_clarify"
            and intent_pred.get("is_ambiguous")
        ):
            answer_before_clarify = pred
            pred = "UNKNOWN"
            clarify_applied = True
            em, f1 = evaluate_prediction(pred, gold_answers)

        total_em += em
        total_f1 += f1

        row: Dict[str, Any] = {
            "id": qid,
            "question": question,
            "prediction": pred,
            "raw_prediction": raw_pred,
            "gold_answers": gold_answers,
            "em": em,
            "f1": f1,
            "generator_status": gen_status,
            "attempts": attempts,
            "retrieved_triples": [
                {"subject": t.subject, "predicate": t.predicate, "object": t.obj} for t in retrieved
            ],
            "evidence_support": evidence_support,
            "evidence_violation": bool(violation),
            "enforcement_action": enforcement_action,
            "raw_answer": (raw_answer if args.contract_variant in ("answer_plus_evidence", "answer_plus_evidence_guardrail_v2") else raw_pred),
            "final_answer": pred,
            "retry_attempted": retry_attempted,
        }
        if args.contract_variant in ("answer_plus_evidence", "answer_plus_evidence_guardrail_v2"):
            row["evidence_line_ids"] = evidence_ids
            if evidence_meta is not None:
                row["evidence_parse"] = evidence_meta
            if raw_answer_retry is not None:
                row["raw_answer_retry"] = raw_answer_retry
                row["evidence_line_ids_retry"] = evidence_line_ids_retry
                row["evidence_support_retry"] = evidence_support_retry
                row["evidence_violation_retry"] = evidence_violation_retry
                row["final_answer_after_retry"] = final_answer_after_retry

        if clarify_applied:
            row["clarify_applied"] = True
            row["answer_before_clarify"] = answer_before_clarify

        # IntentEngine per-sample 工件（可关开）
        if intent_pred is not None and intent_audit is not None:
            row["intent_pred"] = {
                "intents": intent_pred.get("intents"),
                "is_multi_intent": intent_pred.get("is_multi_intent"),
                "is_ambiguous": intent_pred.get("is_ambiguous"),
                "clarification_question": intent_pred.get("clarification_question"),
                "clarification_options": intent_pred.get("clarification_options"),
            }
            row["intent_audit"] = {
                "rules_version_sha": intent_audit.get("rules_version_sha"),
                "thresholds": intent_audit.get("thresholds"),
                "config_fingerprint_intent": intent_audit.get("config_fingerprint_intent"),
            }

        per_sample_results.append(row)

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
    parser.add_argument(
        "--top_k",
        type=int,
        default=10,
        help="Number of triples to retrieve per question",
    )
    parser.add_argument(
        "--ablation",
        type=str,
        default=None,
        help="Ablation label, e.g. 'topk_sweep' or 'retriever_variant'",
    )
    parser.add_argument(
        "--retriever_type",
        type=str,
        default="simple",
        choices=["simple", "bm25"],
        help="Retriever variant: simple lexical or bm25-like",
    )
    parser.add_argument(
        "--contract_variant",
        type=str,
        default="answer_only",
        choices=["answer_only", "answer_plus_evidence", "guardrail_answerable_only", "answer_plus_evidence_guardrail_v2"],
        help="Prompt contract variant / 输出契约变体。",
    )
    parser.add_argument(
        "--enforcement_policy",
        type=str,
        default="",
        help="Enforcement policy when support < 0.5: force_unknown_if_support_lt_0.5 | retry_once_if_support_lt_0.5_else_force_unknown. Default for guardrail_v2: force_unknown_if_support_lt_0.5.",
    )
    parser.add_argument(
        "--intent_mode",
        type=str,
        default="none",
        choices=["none", "rule_v1", "rule_v1_route", "rule_v1_clarify"],
        help="Intent module mode: none（关闭）/ rule_v1（仅打标）/ rule_v1_route（路由）/ rule_v1_clarify（路由+澄清）。",
    )
    args = parser.parse_args()

    set_seed(args.seed)

    exp_id = args.output_id or f"exp_baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = RUNS_DIR / exp_id
    artifacts_dir = ensure_dir(run_dir / "artifacts")

    logger = DualLogger(run_dir, "run.log")
    start_time = datetime.now().isoformat()

    # 避免在日志中泄露 API Key：对 --api_key 参数做脱敏
    redacted_argv: list[str] = []
    skip_next = False
    for i, tok in enumerate(sys.argv):
        if skip_next:
            skip_next = False
            continue
        if tok == "--api_key" and i + 1 < len(sys.argv):
            redacted_argv.extend(["--api_key", "****"])
            skip_next = True
        else:
            redacted_argv.append(tok)

    logger.log(f"argv: {' '.join(redacted_argv)}")
    logger.log(f"Baseline experiment started (run_id={exp_id})")

    # 真实模式下先做一次生成端健康检查，避免产生“半跑”工件
    if not args.mock:
        ok, msg = _probe_endpoint(args.base_url, args.model, args.api_key)
        if not ok:
            logger.log(f"FATAL: generator probe failed: {msg}")
            logger.close()
            print(f"Generator probe failed: {msg}", file=sys.stderr)
            return 1

    try:
        metrics, per_sample = run_experiment(args, log_fn=logger.log)
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
    run_mode = "mock" if args.mock else "real"
    backend = "openai_compatible"
    endpoint_fingerprint = {
        "base_url": args.base_url,
        "model": args.model,
    }
    if args.contract_variant == "answer_plus_evidence":
        prompt_contract_version = PROMPT_CONTRACT_VERSION_ANSWER_EVIDENCE
    elif args.contract_variant == "guardrail_answerable_only":
        prompt_contract_version = PROMPT_CONTRACT_VERSION_GUARDRAIL
    elif args.contract_variant == "answer_plus_evidence_guardrail_v2":
        prompt_contract_version = PROMPT_CONTRACT_VERSION_ANSWER_EVIDENCE_GUARDRAIL_V2
    else:
        prompt_contract_version = PROMPT_CONTRACT_VERSION

    default_cfg, config_fingerprint = _load_default_config_and_fingerprint()
    overrides: list[str] = []
    if default_cfg:
        gen_cfg = default_cfg.get("generator", {})
        def_base = gen_cfg.get("base_url")
        if def_base is not None and args.base_url != def_base:
            overrides.append("base_url")
        def_model = gen_cfg.get("model")
        if def_model is not None and args.model != def_model:
            overrides.append("model")
        ret_cfg = default_cfg.get("retriever", {})
        def_ret = ret_cfg.get("type")
        if def_ret is not None and args.retriever_type != def_ret:
            overrides.append("retriever_type")
        def_topk = ret_cfg.get("topk")
        if def_topk is not None and args.top_k != def_topk:
            overrides.append("top_k")
        if args.contract_variant == "answer_plus_evidence_guardrail_v2":
            g_cfg = default_cfg.get("guardrail", {})
            def_policy = g_cfg.get("enforcement_policy")
            policy_arg = (args.enforcement_policy or "").strip()
            if def_policy is not None and policy_arg and policy_arg != def_policy:
                overrides.append("enforcement_policy")

    if args.contract_variant == "answer_plus_evidence_guardrail_v2":
        guardrail_version = "evidence_bounded_v2"
        policy = (args.enforcement_policy or "").strip()
        if not policy and default_cfg:
            policy = (default_cfg.get("guardrail") or {}).get("enforcement_policy", "")
        enforcement_policy = policy or "force_unknown_if_support_lt_0.5"
        support_semantics_version = "raw_answer_only_v1"
        from framework.evidence_support import get_module_sha256  # type: ignore

        support_module_sha256 = get_module_sha256()
    else:
        guardrail_version = None
        enforcement_policy = "none"
        support_semantics_version = None
        support_module_sha256 = None

    eval_sha = ""
    eval_path = ROOT / "framework" / "eval.py"
    if eval_path.exists():
        try:
            eval_sha = hashlib.sha256(eval_path.read_bytes()).hexdigest()
        except Exception:
            pass
    api_key_source = None
    if not args.mock and args.api_key:
        api_key_source = _API_KEY_SOURCE if (args.api_key == _API_KEY and _API_KEY_SOURCE) else "cli"

    # IntentEngine 审计字段
    intent_module_enabled = args.intent_mode != "none"
    intent_rules_sha256 = None
    intent_taxonomy_sha256 = None
    intent_thresholds = None
    intent_config_fingerprint_intent = None
    if intent_module_enabled:
        from src.intent.intent_engine import IntentEngine as _IE  # type: ignore

        _ie = _IE()
        _info = _ie.get_audit_info()
        intent_rules_sha256 = _info.get("rules_version_sha")
        intent_taxonomy_sha256 = _info.get("taxonomy_sha256")
        intent_thresholds = _info.get("thresholds")
        intent_config_fingerprint_intent = _info.get("config_fingerprint_intent")

    # Intent 统计汇总（从 per-sample 反推）
    intent_multi_intent_rate = None
    intent_ambiguous_rate = None
    intent_coverage_rate = None
    if intent_module_enabled:
        n_samples = len(per_sample)
        if n_samples > 0:
            n_multi = 0
            n_amb = 0
            n_with_any_intent = 0
            for s in per_sample:
                ip = s.get("intent_pred") or {}
                intents = ip.get("intents") or []
                if intents:
                    n_with_any_intent += 1
                if ip.get("is_multi_intent"):
                    n_multi += 1
                if ip.get("is_ambiguous"):
                    n_amb += 1
            intent_multi_intent_rate = n_multi / n_samples
            intent_ambiguous_rate = n_amb / n_samples
            intent_coverage_rate = n_with_any_intent / n_samples
    audit = {
        "eval_tokenizer": "mixed_zh_char_en_word_v1",
        "eval_py_sha256": eval_sha,
        "eval_remove_en_articles": True,
        "normalize_rules": "lower, remove_punc(en+cn), white_space_fix",
        "config_fingerprint": config_fingerprint or None,
        "audit_overrides": overrides if overrides else None,
        "api_key_source": api_key_source,
        "generator_parse_version": GENERATOR_PARSE_VERSION,
        "retry_policy": f"max_attempts={RETRY_MAX}",
        "prompt_contract_version": prompt_contract_version,
        "contract_variant": args.contract_variant,
        "guardrail_version": guardrail_version,
        "enforcement_policy": enforcement_policy,
        "support_semantics_version": support_semantics_version,
        "support_module_sha256": support_module_sha256,
        # Intent module audit
        "intent_module_enabled": intent_module_enabled,
        # 兼容旧字段命名（*_sha256），同时增加更简洁的别名与指纹字段
        "intent_rules_sha256": intent_rules_sha256,
        "intent_taxonomy_sha256": intent_taxonomy_sha256,
        "intent_rules_sha": intent_rules_sha256,
        "intent_taxonomy_sha": intent_taxonomy_sha256,
        "intent_thresholds": intent_thresholds,
        "intent_config_fingerprint": intent_config_fingerprint_intent,
        "intent_multi_intent_rate": intent_multi_intent_rate,
        "intent_ambiguous_rate": intent_ambiguous_rate,
        "intent_coverage_rate": intent_coverage_rate,
        "intent_mode": args.intent_mode,
        "run_mode": run_mode,
        "ablation": args.ablation,
        "generator_backend": backend,
        "generator_endpoint_fingerprint": endpoint_fingerprint,
        "generator_temperature": GEN_TEMPERATURE,
        "generator_top_p": GEN_TOP_P,
        "generator_max_tokens": GEN_MAX_TOKENS,
        "seed": args.seed,
        "retriever_topk": args.top_k,
        "retriever_type": args.retriever_type,
    }
    metrics.setdefault("audit", {}).update(audit)
    core_metrics.save_metrics(metrics, metrics_path)
    save_jsonl(per_sample, artifacts_dir / "per_sample_results.jsonl")

    gen_status_rows = [
        {"id": s.get("id"), "generator_status": s.get("generator_status", ""), "attempts": s.get("attempts", 1)}
        for s in per_sample
    ]
    save_jsonl(gen_status_rows, artifacts_dir / "per_sample_generator_status.jsonl")

    # 记录本次运行使用的 prompt 契约模板（方便审计和复现）
    if args.contract_variant == "answer_plus_evidence":
        prompt_template = (
            "=== System ===\n"
            "你是一个知识库问答助手。输出契约：严格输出两行，且不要添加多余文本或解释。\n"
            "Line1: ANSWER: <最终答案或 UNKNOWN>\n"
            "Line2: EVIDENCE: <逗号分隔的行号，范围 1..K，对应给定 triples 的行号>\n\n"
            "=== User (结构) ===\n"
            "[Triples]\n每行格式: [i] subject: X\tpredicate: Y\tobject: Z\n"
            "[Task]\n请仅根据上述 triples 回答，并按上述两行格式输出。\n"
            f"prompt_contract_version={PROMPT_CONTRACT_VERSION_ANSWER_EVIDENCE}"
        )
    elif args.contract_variant == "answer_plus_evidence_guardrail_v2":
        prompt_template = (
            "=== System ===\n"
            "你是一个知识库问答助手。输出契约：严格输出两行，且不要添加多余文本或解释。\n"
            "Line1: ANSWER: <最终答案或 UNKNOWN>\n"
            "Line2: EVIDENCE: <逗号分隔的行号，范围 1..K，对应给定 triples 的行号>\n"
            "硬性约束：ANSWER 必须完全由 EVIDENCE 行中的内容（subject/object/数值/术语）拷贝或轻微改写得到；\n"
            "若在任何 EVIDENCE 行中都找不到能支撑答案的内容，必须输出 UNKNOWN；"
            "禁止使用 triples 之外的常识或背景知识；禁止解释；禁止多行输出。\n\n"
            "=== User (结构) ===\n"
            "[Triples]\n每行格式: [i] subject: X\tpredicate: Y\tobject: Z\n"
            "[Task]\n请先选择支撑答案的 EVIDENCE 行号，然后仅基于这些 EVIDENCE 行构造答案；"
            "若无法从 EVIDENCE 中得到答案，则输出 UNKNOWN。\n"
            f"prompt_contract_version={PROMPT_CONTRACT_VERSION_ANSWER_EVIDENCE_GUARDRAIL_V2}, "
            "guardrail_version=evidence_bounded_v2"
        )
    elif args.contract_variant == "guardrail_answerable_only":
        prompt_template = (
            "=== System ===\n"
            "你是一个知识库问答助手。硬性约束：只能从给定 triples 中提取答案，绝对禁止编造不在 triples 中出现的事实；"
            "若无法从 triples 得到答案，必须输出 UNKNOWN。输出契约：只输出最终答案或 UNKNOWN，不要解释。\n\n"
            "=== User (结构) ===\n"
            "[Triples]\n每行格式: subject: X\tpredicate: Y\tobject: Z\n"
            "[Task]\n请仅根据上述 triples 回答。无法确定答案时必须输出 UNKNOWN，禁止凭常识或背景知识猜测。\n"
            f"prompt_contract_version={PROMPT_CONTRACT_VERSION_GUARDRAIL}"
        )
    else:
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

    # 仅在 Answer+Evidence 合同下，输出 evidence 相关诊断工件
    if args.contract_variant in ("answer_plus_evidence", "answer_plus_evidence_guardrail_v2"):
        # 1) evidence 行解析成功率等
        parse_rows = [s.get("evidence_parse") for s in per_sample if s.get("evidence_parse") is not None]
        total = len(parse_rows)
        if total > 0:
            def _rate(fn) -> float:
                return sum(1 for r in parse_rows if fn(r)) / total if total else 0.0

            parse_summary = {
                "n": total,
                "parse_success_rate": _rate(lambda r: r.get("has_evidence_line") and not r.get("evidence_out_of_range") and not r.get("evidence_empty")),
                "has_evidence_line_rate": _rate(lambda r: r.get("has_evidence_line")),
                "empty_evidence_rate": _rate(lambda r: r.get("evidence_empty")),
                "out_of_range_rate": _rate(lambda r: r.get("evidence_out_of_range")),
                "has_duplicate_rate": _rate(lambda r: r.get("evidence_has_duplicate")),
            }
        else:
            parse_summary = {
                "n": 0,
                "parse_success_rate": 0.0,
                "has_evidence_line_rate": 0.0,
                "empty_evidence_rate": 0.0,
                "out_of_range_rate": 0.0,
                "has_duplicate_rate": 0.0,
            }
        (artifacts_dir / "evidence_line_parse_report.json").write_text(
            json.dumps(parse_summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 2) evidence 支持率诊断
        evidence_support = _compute_evidence_support_summary(per_sample)
        (artifacts_dir / "evidence_support_summary.json").write_text(
            json.dumps(evidence_support, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Guardrail v2 专属：证据违约与执行策略统计
    if args.contract_variant == "answer_plus_evidence_guardrail_v2":
        total_n = len(per_sample)
        violation_ids = [s.get("id", "") for s in per_sample if s.get("evidence_violation")]
        from collections import Counter

        action_counter = Counter(s.get("enforcement_action", "none") for s in per_sample)
        violation_rate = len(violation_ids) / total_n if total_n else 0.0
        violation_report = {
            "n": total_n,
            "evidence_violation_rate": violation_rate,
            "violation_ids": violation_ids,
            "enforcement_action_counts": dict(action_counter),
        }
        (artifacts_dir / "evidence_violation_report.json").write_text(
            json.dumps(violation_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

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

