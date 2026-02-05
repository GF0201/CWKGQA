## P4 一致性只读校验报告（P4_consistency_report）

- 生成时间：2026-02-05T21:19:31
- 索引文件：`D:/KGELLM/kgqa_framework/intent_workspace/runs/_index/index.jsonl`

本报告由只读脚本 `paper_pack/validation/validate_paper_pack_consistency.py` 自动生成，
仅读取 `intent_workspace/runs/_index/index.jsonl`、对应 run 目录中的 `metrics.json`，
以及 `intent_workspace/artifacts/` 下的若干 CSV/JSON 文件，不对这些目录中的任何文件进行修改。

### (a) 主线 run config_fingerprint 一致性
- 结果：**FAIL**
- 详情：
  - run_id=intent_20260205_183901_default_guardrail_v2_policyR_none: config_fingerprint 缺失或为空（应补齐以固定默认真实配置指纹）。
  - 非空 config_fingerprint 唯一且一致：be8a5584eb38a885f3a804f195808b444fd4cd3ad304a185352271fea6661140
    覆盖 run_id：intent_20260205_183902_default_guardrail_v2_policyR_rule_v1, intent_20260205_183903_default_guardrail_v2_policyR_rule_v1_route, intent_20260205_183904_default_guardrail_v2_policyR_rule_v1_clarify
  建议：在修复缺失或不一致后，重新运行本脚本以确认主线 run 的默认真实配置指纹已固定。

### (b) 启用 intent 的 run 审计字段完整性
- 结果：**FAIL**
- 详情：
  - run_id=intent_20260205_183902_default_guardrail_v2_policyR_rule_v1: 审计字段 `rules_sha` 缺失或为空。
  - run_id=intent_20260205_183902_default_guardrail_v2_policyR_rule_v1: 审计字段 `taxonomy_sha` 缺失或为空。
  - run_id=intent_20260205_183902_default_guardrail_v2_policyR_rule_v1: 审计字段 `thresholds` 缺失或为空。
  - run_id=intent_20260205_183902_default_guardrail_v2_policyR_rule_v1: 审计字段 `intent_config_fingerprint` 缺失或为空。
  - run_id=intent_20260205_183903_default_guardrail_v2_policyR_rule_v1_route: 审计字段 `rules_sha` 缺失或为空。
  - run_id=intent_20260205_183903_default_guardrail_v2_policyR_rule_v1_route: 审计字段 `taxonomy_sha` 缺失或为空。
  - run_id=intent_20260205_183903_default_guardrail_v2_policyR_rule_v1_route: 审计字段 `thresholds` 缺失或为空。
  - run_id=intent_20260205_183903_default_guardrail_v2_policyR_rule_v1_route: 审计字段 `intent_config_fingerprint` 缺失或为空。
  - run_id=intent_20260205_183904_default_guardrail_v2_policyR_rule_v1_clarify: 审计字段 `rules_sha` 缺失或为空。
  - run_id=intent_20260205_183904_default_guardrail_v2_policyR_rule_v1_clarify: 审计字段 `taxonomy_sha` 缺失或为空。
  - run_id=intent_20260205_183904_default_guardrail_v2_policyR_rule_v1_clarify: 审计字段 `thresholds` 缺失或为空。
  - run_id=intent_20260205_183904_default_guardrail_v2_policyR_rule_v1_clarify: 审计字段 `intent_config_fingerprint` 缺失或为空。
  结论：当前启用 intent 的 run 在 metrics.json.audit 中缺少部分审计字段，建议补齐上述字段后重新运行本脚本。

### (c) artifacts 中 intent_mode 集合与索引一致性
- 结果：**PASS**
- 详情：
  - 参考 intent_mode 集合（来自 intent_ablation_main_table.csv）：['none', 'rule_v1', 'rule_v1_clarify', 'rule_v1_route']
  - intent_ablation_compare.json 中的 intent_mode 集合与 CSV 参考集合一致。
  - intent_trigger_stats.csv 覆盖的 intent_mode 集合为 ['rule_v1', 'rule_v1_clarify', 'rule_v1_route']，是参考集合的子集（仅包含启用 intent 的模式）。
  - threshold_sweep_summary.csv 与 rules_trigger_frequency.csv 当前 schema 不含 intent_mode 字段，本检查视为 N/A（不记为 FAIL）。
  结论：当前 artifacts 中显式或可推导的 intent_mode 集合与索引及参考 CSV 一致，未发现缺失或多余的模式标签。

### (d) input_hash 为空值检测
- 结果：**FAIL**
- 详情：
  以下 run 在 runs/_index/index.jsonl 中的 input_hash 为空或缺失：
  - run_id=intent_20260205_183901_default_guardrail_v2_policyR_none
  - run_id=intent_20260205_183902_default_guardrail_v2_policyR_rule_v1
  - run_id=intent_20260205_183903_default_guardrail_v2_policyR_rule_v1_route
  - run_id=intent_20260205_183904_default_guardrail_v2_policyR_rule_v1_clarify
  说明：本脚本仅记录缺失情况，不尝试推导或写回任何 input_hash 值。

### 手工复核指引

- 如需手工复核配置指纹一致性，请对照以下文件：
  - `runs/_index/index.jsonl` 中各 run 的 `config_fingerprint` 字段；
  - 对应 run 目录下的 `metrics.json`（尤其是 `audit.config_fingerprint` 字段）；
  - 若存在，与 Intent 相关的 `metrics.json.audit` 其它字段。
- 如需复核 intent_mode 集合，请对照：
  - `artifacts/intent_ablation_main_table.csv` 与 `artifacts/intent_ablation_compare.json`；
  - `artifacts/intent_trigger_stats.csv` 与其在 LaTeX 表中的对应行。
- 如需复核 input_hash 情况，请直接查看 `runs/_index/index.jsonl` 中相应 run 的字段。
