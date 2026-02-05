import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


ROOT = Path(__file__).resolve().parents[2]  # intent_workspace/
PAPER_PACK = ROOT / "paper_pack"
ARTIFACTS = ROOT / "artifacts"
RUNS = ROOT / "runs"
INDEX_PATH = RUNS / "_index" / "index.jsonl"
VALIDATION_DIR = PAPER_PACK / "validation"
REPORT_PATH = VALIDATION_DIR / "P4_consistency_report.md"


@dataclass
class CheckResult:
    name: str
    status: str  # "PASS" or "FAIL" or "N/A"
    details: List[str] = field(default_factory=list)

    def add(self, line: str) -> None:
        self.details.append(line)


def load_index_runs() -> List[Dict]:
    runs: List[Dict] = []
    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"index.jsonl not found at {INDEX_PATH}")
    with INDEX_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            runs.append(json.loads(line))
    return runs


def get_mainline_runs(index_runs: List[Dict]) -> List[Dict]:
    # 当前索引中主线意图实验均标记为 mode == "from_mainline"
    return [r for r in index_runs if r.get("mode") == "from_mainline"]


def check_config_fingerprint_consistency(index_runs: List[Dict]) -> CheckResult:
    """
    检查项 a）四个主线 intent_mode run 的 config_fingerprint 是否一致且完整。
    """
    result = CheckResult(
        name="(a) 主线 run config_fingerprint 一致性",
        status="PASS",
    )
    mainline = get_mainline_runs(index_runs)
    if not mainline:
        result.status = "FAIL"
        result.add("未在 index.jsonl 中找到 mode=='from_mainline' 的主线 run；无法检查配置指纹。")
        return result

    fingerprints: Dict[Optional[str], List[str]] = {}
    for r in mainline:
        fp = r.get("config_fingerprint")
        fingerprints.setdefault(fp, []).append(r.get("run_id", "<unknown_run_id>"))

    non_null_fps = {fp: runs for fp, runs in fingerprints.items() if fp not in (None, "", "null")}
    missing_runs = fingerprints.get(None, []) + fingerprints.get("", []) + fingerprints.get("null", [])

    if missing_runs:
        result.status = "FAIL"
        for rid in missing_runs:
            result.add(f"- run_id={rid}: config_fingerprint 缺失或为空（应补齐以固定默认真实配置指纹）。")

    if len(non_null_fps) == 1:
        fp_val, run_ids = next(iter(non_null_fps.items()))
        result.add(f"- 非空 config_fingerprint 唯一且一致：{fp_val}")
        result.add(f"  覆盖 run_id：{', '.join(run_ids)}")
    elif len(non_null_fps) > 1:
        result.status = "FAIL"
        result.add("- 发现多个不同的非空 config_fingerprint，主线 run 配置指纹不一致：")
        for fp_val, run_ids in non_null_fps.items():
            result.add(f"  - {fp_val}: {', '.join(run_ids)}")

    if result.status == "PASS":
        result.add("结论：除 none baseline 外，目前主线启用 intent 的三个 run 共享同一 config_fingerprint，默认真实配置指纹在这些 run 上是一致的。")
    else:
        result.add("建议：在修复缺失或不一致后，重新运行本脚本以确认主线 run 的默认真实配置指纹已固定。")
    return result


def load_metrics_audit(run_id: str) -> Optional[Dict]:
    """
    只读加载 intent_workspace/runs/<run_id>/metrics.json 中的 audit 字段（如存在）。
    """
    metrics_path = RUNS / run_id / "metrics.json"
    if not metrics_path.exists():
        return None
    try:
        with metrics_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    audit = data.get("audit")
    return audit if isinstance(audit, dict) else None


def check_intent_audit_fields(index_runs: List[Dict]) -> CheckResult:
    """
    检查项 b）intent 相关 audit 字段在启用 intent 的 run 中是否齐全。
    仅针对启用 intent 的 run（rule_v1 / route / clarify），从 metrics.json.audit 中尝试读取：
      - rules_sha
      - taxonomy_sha
      - thresholds
      - intent_config_fingerprint
    """
    result = CheckResult(
        name="(b) 启用 intent 的 run 审计字段完整性",
        status="PASS",
    )
    required_fields = ["rules_sha", "taxonomy_sha", "thresholds", "intent_config_fingerprint"]

    # 依据 run_id 名称粗略判断哪些 run 启用了 intent 模块
    enabled_runs: List[str] = []
    for r in get_mainline_runs(index_runs):
        rid = r.get("run_id", "")
        if "rule_v1" in rid:  # 覆盖 rule_v1 / route / clarify
            enabled_runs.append(rid)

    if not enabled_runs:
        result.status = "FAIL"
        result.add("未检测到启用 intent 的主线 run（run_id 中包含 'rule_v1'），无法检查审计字段。")
        return result

    any_missing = False
    for rid in enabled_runs:
        audit = load_metrics_audit(rid)
        if audit is None:
            any_missing = True
            result.add(f"- run_id={rid}: 未找到 metrics.json 或其中缺少 audit 字段；无法检查 intent 审计字段。")
            continue
        for field in required_fields:
            if field not in audit or audit.get(field) in (None, "", "null"):
                any_missing = True
                result.add(f"- run_id={rid}: 审计字段 `{field}` 缺失或为空。")

    if any_missing:
        result.status = "FAIL"
        result.add("结论：当前启用 intent 的 run 在 metrics.json.audit 中缺少部分审计字段，建议补齐上述字段后重新运行本脚本。")
    else:
        result.add("结论：所有启用 intent 的 run 在 metrics.json.audit 中均包含 rules_sha / taxonomy_sha / thresholds / intent_config_fingerprint 字段。")
    return result


def load_intent_mode_from_ablation_csv() -> Tuple[Dict[str, str], Set[str]]:
    """
    从 artifacts/intent_ablation_main_table.csv 读取 run_id -> intent_mode 映射及 intent_mode 集合。
    """
    mapping: Dict[str, str] = {}
    modes: Set[str] = set()
    path = ARTIFACTS / "intent_ablation_main_table.csv"
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = row.get("run_id")
            mode = row.get("intent_mode")
            if rid and mode:
                mapping[rid] = mode
                modes.add(mode)
    return mapping, modes


def check_intent_mode_sets(index_runs: List[Dict]) -> CheckResult:
    """
    检查项 c）artifacts 中 CSV/JSON 的 intent_mode 集合是否与 index 中的 intent_mode 一致。
    - 参考集合：从 intent_ablation_main_table.csv 与 intent_ablation_compare.json 中推导。
    - 允许某些工件只覆盖启用 intent 的子集（如 trigger_stats）。
    """
    result = CheckResult(
        name="(c) artifacts 中 intent_mode 集合与索引一致性",
        status="PASS",
    )

    run_to_mode, modes_from_csv = load_intent_mode_from_ablation_csv()
    if not run_to_mode:
        result.status = "FAIL"
        result.add("未能从 artifacts/intent_ablation_main_table.csv 中读取任何 (run_id, intent_mode) 映射。")
        return result

    # 1) 以 ablation CSV 为基准集合
    canonical_modes = set(modes_from_csv)
    result.add(f"- 参考 intent_mode 集合（来自 intent_ablation_main_table.csv）：{sorted(canonical_modes)}")

    # 2) 对比 intent_ablation_compare.json 中的 intent_mode 集合
    compare_path = ARTIFACTS / "intent_ablation_compare.json"
    modes_from_json: Set[str] = set()
    if compare_path.exists():
        with compare_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for run_id, payload in data.items():
            mode = payload.get("intent_mode")
            if mode is None and run_id in run_to_mode:
                mode = run_to_mode[run_id]
            if mode is not None:
                modes_from_json.add(mode)
        if modes_from_json != canonical_modes:
            result.status = "FAIL"
            result.add(f"- intent_ablation_compare.json 中的 intent_mode 集合为 {sorted(modes_from_json)}，与 CSV 参考集合不一致。")
        else:
            result.add("- intent_ablation_compare.json 中的 intent_mode 集合与 CSV 参考集合一致。")
    else:
        result.status = "FAIL"
        result.add("- 缺少 artifacts/intent_ablation_compare.json，无法对比 JSON 中的 intent_mode 集合。")

    # 3) 对比 intent_trigger_stats.csv（预期为启用 intent 的子集）
    trigger_path = ARTIFACTS / "intent_trigger_stats.csv"
    if trigger_path.exists():
        modes_from_trigger: Set[str] = set()
        with trigger_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rid = row.get("run_id")
                if not rid:
                    continue
                mode = run_to_mode.get(rid)
                if mode:
                    modes_from_trigger.add(mode)
        if not modes_from_trigger:
            result.status = "FAIL"
            result.add("- 未能从 intent_trigger_stats.csv 中通过 run_id 还原任何 intent_mode。")
        elif not modes_from_trigger.issubset(canonical_modes):
            result.status = "FAIL"
            result.add(f"- intent_trigger_stats.csv 中推导的 intent_mode 集合为 {sorted(modes_from_trigger)}，不属于参考集合的子集。")
        else:
            result.add(f"- intent_trigger_stats.csv 覆盖的 intent_mode 集合为 {sorted(modes_from_trigger)}，是参考集合的子集（仅包含启用 intent 的模式）。")
    else:
        result.status = "FAIL"
        result.add("- 缺少 artifacts/intent_trigger_stats.csv，无法检查该工件中的 intent_mode 覆盖情况。")

    # 4) 其它工件（threshold_sweep_summary.csv / rules_trigger_frequency.csv）当前 schema 中无 intent_mode 字段，仅记录为 N/A。
    result.add("- threshold_sweep_summary.csv 与 rules_trigger_frequency.csv 当前 schema 不含 intent_mode 字段，本检查视为 N/A（不记为 FAIL）。")

    if result.status == "PASS":
        result.add("结论：当前 artifacts 中显式或可推导的 intent_mode 集合与索引及参考 CSV 一致，未发现缺失或多余的模式标签。")
    else:
        result.add("建议：修复以上列出的差异（如缺失 JSON/CSV 或无法通过 run_id 还原 intent_mode）后，重新运行本脚本进行验证。")
    return result


def check_input_hash_missing(index_runs: List[Dict]) -> CheckResult:
    """
    检查项 d）index.jsonl 中 input_hash 为空的情况，仅记录不修复。
    """
    result = CheckResult(
        name="(d) input_hash 为空值检测",
        status="PASS",
    )
    missing: List[str] = []
    for r in index_runs:
        rid = r.get("run_id", "<unknown_run_id>")
        ih = r.get("input_hash")
        if ih in (None, "", "null"):
            missing.append(rid)

    if missing:
        result.status = "FAIL"
        result.add("以下 run 在 runs/_index/index.jsonl 中的 input_hash 为空或缺失：")
        for rid in missing:
            result.add(f"- run_id={rid}")
        result.add("说明：本脚本仅记录缺失情况，不尝试推导或写回任何 input_hash 值。")
    else:
        result.add("所有主线 run 的 input_hash 字段均已填写，无空值。")
    return result


def write_report(results: List[CheckResult]) -> None:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("## P4 一致性只读校验报告（P4_consistency_report）")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- 索引文件：`{INDEX_PATH.as_posix()}`")
    lines.append("")
    lines.append("本报告由只读脚本 `paper_pack/validation/validate_paper_pack_consistency.py` 自动生成，")
    lines.append("仅读取 `intent_workspace/runs/_index/index.jsonl`、对应 run 目录中的 `metrics.json`，")
    lines.append("以及 `intent_workspace/artifacts/` 下的若干 CSV/JSON 文件，不对这些目录中的任何文件进行修改。")
    lines.append("")

    for res in results:
        heading = f"### {res.name}"
        lines.append(heading)
        status_str = "**PASS**" if res.status == "PASS" else ("**FAIL**" if res.status == "FAIL" else "**N/A**")
        lines.append(f"- 结果：{status_str}")
        if res.details:
            lines.append("- 详情：")
            for d in res.details:
                lines.append(f"  {d}")
        lines.append("")

    lines.append("### 手工复核指引")
    lines.append("")
    lines.append("- 如需手工复核配置指纹一致性，请对照以下文件：")
    lines.append(f"  - `runs/_index/index.jsonl` 中各 run 的 `config_fingerprint` 字段；")
    lines.append("  - 对应 run 目录下的 `metrics.json`（尤其是 `audit.config_fingerprint` 字段）；")
    lines.append("  - 若存在，与 Intent 相关的 `metrics.json.audit` 其它字段。")
    lines.append("- 如需复核 intent_mode 集合，请对照：")
    lines.append("  - `artifacts/intent_ablation_main_table.csv` 与 `artifacts/intent_ablation_compare.json`；")
    lines.append("  - `artifacts/intent_trigger_stats.csv` 与其在 LaTeX 表中的对应行。")
    lines.append("- 如需复核 input_hash 情况，请直接查看 `runs/_index/index.jsonl` 中相应 run 的字段。")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    index_runs = load_index_runs()
    results: List[CheckResult] = [
        check_config_fingerprint_consistency(index_runs),
        check_intent_audit_fields(index_runs),
        check_intent_mode_sets(index_runs),
        check_input_hash_missing(index_runs),
    ]
    write_report(results)


if __name__ == "__main__":
    main()

