## Intent paper\_pack 生成记录（CHANGELOG）

### 2026-02-05 — 初始生成（from existing artifacts）

- **生成范围**
  - 在不重新跑实验、不修改任何主线配置或指纹的前提下，从现有 artifacts 与索引文件生成：  
    - 中文正文：`text/intent_module_methods_zh.md`、`text/intent_ablation_results_zh.md`、`text/intent_thresholds_selection_zh.md`、`text/intent_case_study_zh.md`、`text/threats_to_validity_intent_zh.md`、`text/source_files_manifest.md`；
    - LaTeX 表格：`latex/intent_ablation_main_table.tex`、`latex/intent_trigger_stats_table.tex`、`latex/threshold_sweep_table.tex`、`latex/rules_trigger_frequency_table.tex`；
    - 附录：`appendix/intent_audit_fields.md`、`appendix/intent_artifacts_schema.md`、`appendix/intent_error_slices_summary.md`；
    - 导航与记录：`README.md`（本目录导航）与本 `CHANGELOG.md`。

- **直接使用的主线 run 与来源说明**
  - 主线 KGQA 对比实验（四种 intent\_mode）：
    - `exp_default_intent_none_real_v1`
    - `exp_default_intent_rule_v1_real_v1`
    - `exp_default_intent_route_real_v1`
    - `exp_default_intent_clarify_real_v1`
  - 这些 run 的 EM/F1/UNKNOWN 比例与 Intent 统计来自：
    - `intent_workspace/artifacts/intent_ablation_compare.json`
    - `intent_workspace/artifacts/intent_ablation_main_table.csv`
    - `intent_workspace/artifacts/intent_trigger_stats.csv`
    - `intent_workspace/artifacts/error_slices.md`
  - Intent 配置与阈值扫描信息来自：
    - `intent_workspace/artifacts/threshold_sweep_summary.csv`
    - `intent_workspace/README.md`
    - `intent_workspace/artifacts_schema.md`
    - `reports/Task18_20_intent_module_summary.md`
  - intent\_workspace 侧的 run 概览与指纹信息来自：
    - `intent_workspace/runs/_index/index.jsonl`（样例 run：`intent_20260205_183901_default_guardrail_v2_policyR_*`）

- **关键约束与已知缺失**
  - 未对任何实验配置或指纹进行修改；所有哈希值与 key\_metrics 字段均直接从现有 artifacts 读取。
  - `threshold_sweep_summary.csv` 中的 `gold_macro_f1` 与 `gold_accuracy` 列在当前版本为空，因此：
    - 阈值分析仅基于 `ambiguous_rate`、`multi_intent_rate`、`coverage_rate` 与 `n`，不对任务级指标做任何推断；
    - 文本与表格中明确标注了这一缺失。
  - `intent_workspace/runs/_index/index.jsonl` 中样例 run 的 `input_hash` 字段当前为 `null`，后续若补齐该字段，可增强审计完备性，但不影响本次基于比例统计的分析。

- **后续更新建议（若将来扩展 paper\_pack）**
  - 若补充新的主线实验或 Intent 模型版本：
    - 建议在不改动原有配置与指纹的前提下，按照相同流程生成新的 artifacts，并在本 `CHANGELOG.md` 中追加日期与变更条目；
    - 为新版本生成独立的 ablation/sweep/casebook/error\_slices 等文件，避免覆盖当前工件。
  - 若补齐 sweep 的 `gold_macro_f1` / `gold_accuracy`：
    - 应在阈值分析正文与 LaTeX 表中增加相应列，并在新的 changelog 条目中说明“增加了任务级指标维度的阈值对比”，以便与当前版本区分。

本 changelog 仅记录 `paper_pack/` 目录下“写作与排版产物”的演进，不涉及任何实验配置修改或新 run 的引入；实验本身的演进应继续在项目其它报告与日志中单独记录。

### 2026-02-05 — P4 更新（口径统一与阈值状态说明）

- **文本更新**
  - 在 `text/intent_ablation_results_zh.md`、`text/threats_to_validity_intent_zh.md` 与 `README.md` 中新增统一口径句，明确当前对比结果仅针对离线评测子集（n=55）与冻结默认真实配置，结论为描述性统计对比，不作统计显著性或全数据集泛化推断。
  - 在 `text/intent_thresholds_selection_zh.md` 中新增“最终阈值状态”小节，明确阈值 sweep 结果目前仅用于离线分析与方法比较，未写回 `intent_workspace/configs/intent_rules.yaml` 或改变任何主线默认真实配置指纹。
- **约束保持**
  - 本次更新未改动任何实验脚本、配置文件或指纹字段，仅在 paper_pack 文稿中补充说明与口径澄清，保证与现有 artifacts 与索引文件保持一致。
