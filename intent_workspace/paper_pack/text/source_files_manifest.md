## Intent 论文材料来源文件清单（Source Files Manifest）

本清单列出本次生成的中文正文、LaTeX 表格与附录在撰写过程中所引用的所有数据文件及关键字段，方便审计与复现。除非特别说明，所有数值仅在原始工件基础上做了格式化（例如四舍五入到三位小数），未进行任何插值或外推。

### 1. 中文正文：intent_module_methods_zh.md

- **主要来源文件**
  - `intent_workspace/README.md`  
    - 字段/段落：目录用途、每次运行必需产物（A–F）、配置指纹（Config Fingerprint）、索引文件 `runs/_index/index.jsonl` 的字段说明、主线 QA + Intent 对比实验入口与 `--intent_mode` 选项。
  - `reports/Task18_20_intent_module_summary.md`  
    - 字段/段落：IntentEngine v1 的接口设计（`predict()` 返回的 `intents`、`is_multi_intent`、`is_ambiguous` 与澄清问句）、rule_predict 入口与审计字段、主线中接入 IntentEngine 的策略、四种运行模式的行为差异。
  - `intent_workspace/artifacts/threshold_sweep_summary.csv`  
    - 字段：`multi_label_threshold`、`ambiguous_margin`、`min_confidence`、`ambiguous_rate`、`multi_intent_rate`、`coverage_rate`、`n`、`intent_config_fingerprint`。
  - `intent_workspace/runs/_index/index.jsonl`  
    - 字段：`run_id`、`datetime`、`mode`、`config_fingerprint`、`input_path`、`input_hash`、`key_metrics.{ambiguous_rate,multi_intent_rate,coverage_rate}`、`notes`。
- **使用方式**
  - 用于描述 IntentEngine v1 的规则推理、多意图与歧义判定机制，以及审计字段与配置指纹的作用；
  - 未引用任何环境变量具体值，仅在必要时提及变量名（如 `MKEAI_API_KEY` 或 `OPENAI_API_KEY`）。

### 2. 中文正文：intent_ablation_results_zh.md

- **主要来源文件**
  - `intent_workspace/artifacts/intent_ablation_main_table.csv`  
    - 字段：`run_id`、`intent_mode`、`EM`、`F1`、`unknown_rate`、`ungrounded_or_wrong_rate`、`format_mismatch_rate`、`multi_intent_rate`、`ambiguous_rate`、`intent_coverage_rate`、`contract_variant`、`enforcement_policy`、`retriever_type`、`retriever_topk`。
  - `intent_workspace/artifacts/intent_ablation_compare.json`  
    - 字段：每个 run 的 `metrics.{n,EM,F1}`、`unknown_rate`、`intent.module_enabled`、`intent.{multi_intent_rate,ambiguous_rate,coverage_rate}`、`intent_label_top1` 分布、`contract_variant`、`enforcement_policy`、`retriever_type`、`retriever_topk`、`intent_mode`。
  - `intent_workspace/artifacts/intent_trigger_stats.csv`  
    - 字段：`run_id`、`intent_label`、`count`、`ratio`（用于 UNKNOWN / AMBIGUOUS / FACTOID / LIST / FILTER 的 top1 分布）。
  - `intent_workspace/artifacts/error_slices.md`  
    - 字段：表格中的 `intent_label`、`n`、`EM_avg`、`F1_avg`、`unknown_rate`。
- **使用方式**
  - 直接从 CSV/JSON 读取 EM、F1、unknown_rate、多意图率、歧义率与覆盖率，并四舍五入到三位小数后写入正文；
  - 对 top1 意图分布中 UNKNOWN、AMBIGUOUS、FACTOID、LIST、FILTER 的 count 与 ratio 进行引用，用于定性比较不同类别的分布；
  - 使用 error slices 的聚合统计说明不同意图类别上的性能差异，未对原有均值做任何再加工。

### 3. 中文正文：intent_thresholds_selection_zh.md

- **主要来源文件**
  - `intent_workspace/artifacts/threshold_sweep_summary.csv`  
    - 字段：`multi_label_threshold`、`ambiguous_margin`、`min_confidence`、`ambiguous_rate`、`multi_intent_rate`、`coverage_rate`、`n`、`intent_config_fingerprint`、`gold_macro_f1`、`gold_accuracy`（后两列在当前工件中为空值）。
  - `intent_workspace/runs/_index/index.jsonl`  
    - 字段：`config_fingerprint`、`key_metrics.{ambiguous_rate,multi_intent_rate,coverage_rate}`。
- **使用方式**
  - 用于描述阈值搜索空间、ambiguous_rate 与 multi_intent_rate 在不同 `ambiguous_margin` 下的变化趋势；
  - 显式指出 `gold_macro_f1` 与 `gold_accuracy` 列为空，因而不对任务级指标做任何定量推断；
  - 未尝试推断主线 run 的阈值是否与 sweep 表中某一行完全相同，仅在“敏感性分析”层面使用该表。

### 4. 中文正文：intent_case_study_zh.md

- **主要来源文件**
  - `intent_workspace/artifacts/casebook.md`  
    - 段落：Clarify-applied cases（Case 1–3）、Multi-intent cases（Case 4–6）、Route-active cases（Case 7–8）、Failure/boundary cases（Case 9–10）。
    - 字段：`id`、`Question`、`Intent prediction`、`clarification_question`、`clarification_options`、`final_answer`（before/after）、`EM/F1 before → after`、`Triggered rules`、`is_multi_intent`、`is_ambiguous`、`Retrieved triples` 等。
- **使用方式**
  - 对每个选取案例，仅在原有文本基础上做中文总结与“为什么重要”的定性分析；
  - EM/F1 数值直接引用原始案例中的标注，不进行再计算或外推；
  - 未引入任何额外样本或虚构场景。

### 5. 中文正文：threats_to_validity_intent_zh.md

- **主要来源文件**
  - `intent_workspace/README.md`  
    - 字段/段落：主线 QA + Intent 对比实验的入口命令、四种 `--intent_mode` 的定义、索引文件字段与审计要求。
  - `reports/Task18_20_intent_module_summary.md`  
    - 字段/段落：主线中接入 IntentEngine 的方式（审计-only vs 行为改变）、路由与澄清逻辑对检索与答案的影响、可训练模型 v2 的设计与审计。
  - `intent_workspace/runs/_index/index.jsonl`  
    - 字段：`run_id`、`mode`、`config_fingerprint`、`key_metrics.{ambiguous_rate,multi_intent_rate,coverage_rate}`、`notes`。
  - `intent_workspace/artifacts/intent_ablation_compare.json`  
    - 字段：`metrics.n`、`unknown_rate`、`intent.{multi_intent_rate,ambiguous_rate,coverage_rate}`。
  - `intent_workspace/artifacts/intent_trigger_stats.csv`  
    - 字段：`intent_label`、`count`、`ratio`（用于估计 UNKNOWN / AMBIGUOUS 等标签在 55 条样本中的占比）。
  - `intent_workspace/artifacts/error_slices.md`  
    - 字段：`intent_label`、`n`、`EM_avg`、`F1_avg`、`unknown_rate`。
  - `intent_workspace/artifacts/threshold_sweep_summary.csv`  
    - 字段：`intent_config_fingerprint`（用于讨论与主线 `config_fingerprint` 之间的潜在一致性假设）。
- **使用方式**
  - 用于区分 `rule_v1`（审计-only）与 `rule_v1_route` / `rule_v1_clarify`（行为改变）三类模式，并界定各自的适用范围；
  - 用小样本规模（`n ≈ 55`）、标签分布与误差切片说明实验结论的局限性；
  - 讨论 sweep 指纹与主线指纹之间的一致性假设，但不在缺乏显式对齐证据的情况下做出等价声明。

### 6. LaTeX 表格与附录文件

以下文件在 paper_pack 中以 LaTeX 表格或附录形式出现，其内容完全来源于本 manifest 已列出的数据文件：

- `intent_workspace/paper_pack/latex/intent_ablation_main_table.tex`  
  - 来源：`intent_workspace/artifacts/intent_ablation_main_table.csv`、`intent_workspace/artifacts/intent_ablation_compare.json`。
- `intent_workspace/paper_pack/latex/intent_trigger_stats_table.tex`  
  - 来源：`intent_workspace/artifacts/intent_trigger_stats.csv`、`intent_workspace/artifacts/intent_ablation_compare.json`。
- `intent_workspace/paper_pack/latex/intent_trigger_stats_table_full.tex`  
  - 来源：`intent_workspace/artifacts/intent_trigger_stats.csv`（全量行，一一对应 CSV 中的每条 (run_id, intent_label, count, ratio) 记录），表中 Ratio(\%) 列为对 `ratio` 字段乘以 100 后四舍五入到一位小数。
- `intent_workspace/paper_pack/latex/intent_trigger_stats_table_topk.tex`  
  - 来源：`intent_workspace/artifacts/intent_trigger_stats.csv`；在所有 (run_id, intent_label) 组合上按 `ratio` 字段从大到小排序后选取 top-K（K=8）行，并在表注中说明排序与并列处理规则，全量分布见 `intent_trigger_stats_table_full.tex`。
- `intent_workspace/paper_pack/latex/threshold_sweep_table.tex`  
  - 来源：`intent_workspace/artifacts/threshold_sweep_summary.csv`。
- `intent_workspace/paper_pack/latex/rules_trigger_frequency_table.tex`  
  - 来源：`intent_workspace/artifacts/rules_trigger_frequency.csv`。
- `intent_workspace/paper_pack/appendix/intent_audit_fields.md`  
  - 来源：`intent_workspace/runs/_index/index.jsonl` 及上述各 artifacts 中的审计相关字段。
- `intent_workspace/paper_pack/appendix/intent_artifacts_schema.md`  
  - 来源：`intent_workspace/README.md`、`intent_workspace/artifacts_schema.md`（若存在）、以及本清单引用的所有 A–G 工件。
- `intent_workspace/paper_pack/appendix/intent_error_slices_summary.md`  
  - 来源：`intent_workspace/artifacts/error_slices.md`、`intent_workspace/artifacts/intent_trigger_stats.csv`、`intent_workspace/artifacts/intent_ablation_compare.json`；数值均由原始切片文件解析并四舍五入得到，若与 `error_slices.md` 略有出入，以原始切片文件为准。

### 7. 一致性校验脚本与报告

- `intent_workspace/paper_pack/validation/validate_paper_pack_consistency.py`  
  - 来源数据：  
    - `intent_workspace/runs/_index/index.jsonl`（主线意图实验的 run 列表、config_fingerprint 与 key_metrics）；  
    - `intent_workspace/runs/<run_id>/metrics.json`（如存在，用于读取 `audit.*` 字段）；  
    - `intent_workspace/artifacts/intent_ablation_main_table.csv`、`intent_workspace/artifacts/intent_ablation_compare.json`、`intent_workspace/artifacts/intent_trigger_stats.csv`、`intent_workspace/artifacts/threshold_sweep_summary.csv`、`intent_workspace/artifacts/rules_trigger_frequency.csv`。  
  - 使用方式：仅以只读方式扫描上述文件，检查主线 run 配置指纹一致性、启用 intent 的 run 审计字段完整性、各工件中的 intent_mode 集合是否与索引一致，以及 index 中 input_hash 的缺失情况；不修改 `runs/` 与 `artifacts/` 目录下的任何文件。
- `intent_workspace/paper_pack/validation/P4_file_inventory.md`  
  - 来源数据：`intent_workspace/paper_pack/text/`、`intent_workspace/paper_pack/latex/`、`intent_workspace/paper_pack/appendix/`、`intent_workspace/artifacts/`、`intent_workspace/runs/_index/index.jsonl` 的目录结构与抽样可读性检查结果。
- `intent_workspace/paper_pack/validation/P4_consistency_report.md`  
  - 来源数据：由 `validate_paper_pack_consistency.py` 运行时对上述索引与 artifacts 进行只读扫描得到；报告中列出的所有结论均可追溯到 index.jsonl、metrics.json 与各类 CSV/JSON 工件中的显式字段。

在所有这些文件中，若发现某个结论所依赖的字段在原始工件中缺失或与其他文件不一致，将遵循以下原则：

1. 立即中止使用该字段，不在正文或表格中给出未经验证的数值；
2. 在相应附录或本 manifest 中记录缺失/不一致情况，并给出修复建议（例如“重新跑 sweep 以补齐 gold_macro_f1”或“比对 index 与 metrics 中的 ambiguous_rate 差异”）；
3. 仅在可直接从现有工件读取的前提下，使用数值进行定量描述。

