## Intent paper\_pack 导航说明

本目录 `intent_workspace/paper_pack/` 汇总了意图模块（IntentEngine v1）相关的中文正文、LaTeX 表格与附录材料，所有内容均基于已存在的 artifacts 与索引文件生成，无需重新跑实验即可直接拷贝进论文或补充材料。数值和审计字段的来源见 `text/source_files_manifest.md` 与 `appendix/intent_artifacts_schema.md`。

本节对比结果仅针对当前离线评测子集（n=55）与冻结默认真实配置；结论为描述性统计对比，不作统计显著性或全数据集泛化推断。

### 1. 建议粘贴顺序（主文正文）

在撰写论文主体时，推荐按照以下顺序插入各段落（均为中文学术风格）：

1. **Methods（方法）** → `text/intent_module_methods_zh.md`  
   - 介绍 IntentEngine v1 的规则设计、多标签与歧义判定、澄清与路由逻辑，以及与主线 KGQA 的集成与审计字段设计。
2. **Results – Ablation（消融结果）** → `text/intent_ablation_results_zh.md`  
   - 概述四种 `intent_mode`（none / rule\_v1 / rule\_v1\_route / rule\_v1\_clarify）在相同配置下的 EM/F1/UNKNOWN 比例与意图统计对比。
3. **Thresholds（阈值选择）** → `text/intent_thresholds_selection_zh.md`  
   - 基于 `threshold_sweep_summary.csv` 的网格扫描，讨论在覆盖率基本不变的前提下，如何通过调整阈值折中歧义率与多意图率，并明确指出当前 sweep 中缺失任务级指标列。
4. **Case Study（案例分析）** → `text/intent_case_study_zh.md`  
   - 挑选若干 Clarify-applied、多意图、route-active 以及失败/边界案例，说明 Intent 模块如何在高风险样本上暴露不确定性并支持澄清/路由策略。
5. **Threats to Validity（有效性威胁）** → `text/threats_to_validity_intent_zh.md`  
   - 讨论 rule\_v1（审计-only）与 route/clarify（行为改变）模式的边界、小样本与标签分布带来的局限，以及阈值指纹一致性的假设与未来工作。

如需在论文中引用数据来源和字段映射，可在上述各段之后简要提及 `text/source_files_manifest.md` 中的来源清单。

### 2. 表格（LaTeX）插入方式

所有表格均在 `latex/` 子目录下，以 booktabs 风格编写，可通过 `\input{...}` 或直接复制表格环境的方式插入论文：

- **主消融表** → `latex/intent_ablation_main_table.tex`  
  - 展示四种 `intent_mode` 的 EM/F1、UNKNOWN 比例、multi-intent/ambiguous/coverage 等指标（以百分比形式），notes 中说明 `rule_v1` 为审计-only，`rule_v1_route` 与 `rule_v1_clarify` 为行为改变模式。
- **top1 意图分布表** → `latex/intent_trigger_stats_table.tex`  
  - 汇总三条启用 Intent 的 run 的 top1 意图标签分布（FACTOID/LIST/FILTER/AMBIGUOUS/UNKNOWN），用于支撑对 UNKNOWN 与 AMBIGUOUS 占比的讨论。
- **阈值 sweep 子表** → `latex/threshold_sweep_table.tex`  
  - 抽取 `ambiguous_margin=0.15` 的 $3 \times 3$ 子网格，展示阈值组合及其对应的歧义率/多意图率/覆盖率和 `intent_config_fingerprint`；notes 中说明完整 $3 \times 3 \times 3$ 网格见 CSV。
- **规则触发频率表** → `latex/rules_trigger_frequency_table.tex`  
  - 展示当前规则集在主线 run 上的触发频率（rule\_id、label、count、ratio），用于说明哪些规则在 Intent 判定中最为关键。

示例插入方式（按需修改路径）：

```latex
\input{intent_workspace/paper_pack/latex/intent_ablation_main_table}
```

### 3. 附录（Appendix）材料

以下文件适合作为论文附录或补充材料的一部分，用于给出更完整的审计字段与 schema 说明：

- `appendix/intent_audit_fields.md`  
  - 列举主线 KGQA run 与 intent\_workspace run 的审计字段，说明 metrics.json.audit、repro\_manifest.json、config\_snapshot.yaml、runs/\_index/index.jsonl 等文件中与 Intent 相关的关键字段及其作用。
- `appendix/intent_artifacts_schema.md`  
  - 按 A–G 逐一说明本任务使用的 artifacts（intent\_ablation\_compare.json、intent\_ablation\_main\_table.csv、intent\_trigger\_stats.csv、threshold\_sweep\_summary.csv、casebook.md、error\_slices.md、rules\_trigger\_frequency.csv）的 schema、生成方式与 fail-fast 规则。
- `appendix/intent_error_slices_summary.md`  
  - 对 AMBIGUOUS/FACTOID/LIST/UNKNOWN 等切片的样本数与平均 EM/F1/unknown\_rate 做两位小数的近似摘要，并结合 casebook 案例说明澄清与路由策略的启示。

在英文论文中，可以将这些 md 文件的内容翻译或改写为英文附录，同时保留字段名与文件路径的英文原文，以便审计者直接对照代码仓库。

### 4. 数据与字段追溯

所有正文、表格与附录中引用的数值和字段，均可以通过以下文件追溯到具体 artifacts：

- `text/source_files_manifest.md`：逐段列出每个正文文件引用的源文件与字段；
- `appendix/intent_artifacts_schema.md`：给出 A–G 工件的 schema 与生成方式；
- `intent_workspace/runs/_index/index.jsonl`：提供与主线 run 与 intent\_workspace run 之间的配置指纹与 key\_metrics 对齐信息。

在任何字段缺失或不一致的情况下，本次生成的文本会显式标注缺失情况并避免给出新的数值结论；后续若补齐 artifacts，可按相同结构重新生成对应段落与表格。

### 5. 运行一致性校验脚本

为将 Threats 中提到的“尚未完全校验”风险转化为可复核证据，`paper_pack/validation/` 目录下提供了只读一致性校验脚本：

- 脚本路径：`intent_workspace/paper_pack/validation/validate_paper_pack_consistency.py`  
- 功能范围（只读）：  
  - 扫描 `runs/_index/index.jsonl` 中主线意图实验的 `config_fingerprint` 与 `input_hash` 等字段；  
  - 读取对应 run 目录下的 `metrics.json.audit` 字段（如存在），检查 intent 相关审计字段是否齐全；  
  - 对比 `artifacts/intent_ablation_main_table.csv`、`artifacts/intent_ablation_compare.json` 与 `artifacts/intent_trigger_stats.csv` 中的 `intent_mode` 集合是否与索引一致。  
- 报告输出：`paper_pack/validation/P4_consistency_report.md`（Markdown），包含上述检查项的 PASS/FAIL 结果与问题清单。

示例运行方式（假设当前工作目录为仓库根目录）：

```bash
cd intent_workspace
python paper_pack/validation/validate_paper_pack_consistency.py
```

脚本不会修改 `runs/` 与 `artifacts/` 目录下的任何文件；如需修复报告中指出的问题，应手工编辑相关配置或补齐缺失字段后，再次运行脚本复核。

