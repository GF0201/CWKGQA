## Intent 实验工件与 schema 概览（intent\_artifacts\_schema）

本附录基于 `intent_workspace/artifacts_schema.md`、`intent_workspace/README.md` 以及本次任务中使用到的各类 artifacts，梳理 Intent 相关工件的结构与 fail-fast 规则，便于读者理解如何从主线 run 生成分析所需的 JSON/CSV/Markdown 文件。

### 1. intent\_workspace/runs/\<run\_id\>/ 目录

每个 `run_id` 目录下必须包含六类基础工件（A–F），其 schema 已在 `intent_workspace/artifacts_schema.md` 中详细规定：

1. `repro_manifest.json`（环境与配置指纹）
2. `config_snapshot.yaml`（展开后的完整配置）
3. `metrics.json`（总体与按标签的意图指标及审计字段）
4. `per_sample_intent_results.jsonl`（样本级意图预测与规则触发信息）
5. `run.log`（运行日志）
6. `summary.md`（人类可读摘要）

此外，`runs/_index/index.jsonl` 作为跨 run 索引文件，为每次成功运行追加一行记录，字段包括 `run_id`、`datetime`、`mode`、`config_fingerprint`、`input_path`/`input_hash`、`key_metrics` 与 `notes`。

### 2. 主线对比工件：intent\_ablation\_compare.json（A）

- **位置**：`intent_workspace/artifacts/intent_ablation_compare.json`  
- **生成方式**：由 `scripts/intent_ablation_compare.py` 从主线 `runs/<run_id>/metrics.json` 与 per-sample 结果汇总得到（见 `reports/Task18_20_intent_module_summary.md` 第 8 节）。  
- **schema 概要**（按 run\_id 分组）：
  - `metrics`: `{ "n": int, "EM": float, "F1": float }`
  - `unknown_rate`: float
  - `format_mismatch_rate`: float
  - `ungrounded_or_wrong_rate`: float
  - `intent`:  
    - `module_enabled`: bool  
    - `multi_intent_rate`: float | null  
    - `ambiguous_rate`: float | null  
    - `coverage_rate`: float | null
  - `intent_label_top1`:  
    - 映射 `label -> { "count": int, "ratio": float }`
  - 运行上下文：
    - `ablation`: null 或额外标记
    - `contract_variant`: string
    - `enforcement_policy`: string
    - `retriever_type`: string
    - `retriever_topk`: int
    - `intent_mode`: string（none / rule\_v1 / rule\_v1\_route / rule\_v1\_clarify）

本任务中，所有关于主线四个模式的 EM/F1/unknown\_rate 与 Intent 统计，均来自该 JSON 或其对齐的 CSV 版本。

### 3. 主表 CSV：intent\_ablation\_main\_table.csv（B）

- **位置**：`intent_workspace/artifacts/intent_ablation_main_table.csv`  
- **schema**：
  - `run_id`: string
  - `intent_mode`: string
  - `EM`: float
  - `F1`: float
  - `unknown_rate`: float
  - `ungrounded_or_wrong_rate`: float
  - `format_mismatch_rate`: float
  - `multi_intent_rate`: float | 空
  - `ambiguous_rate`: float | 空
  - `intent_coverage_rate`: float | 空
  - `contract_variant`: string
  - `enforcement_policy`: string
  - `retriever_type`: string
  - `retriever_topk`: int

该 CSV 是 `intent_ablation_compare.json` 的压缩表格版，方便直接生成主文 LaTeX 表；本任务中所有主表数值均从此文件读取，并与 JSON 中的对应字段交叉核对。

### 4. 意图标签分布：intent\_trigger\_stats.csv（C）

- **位置**：`intent_workspace/artifacts/intent_trigger_stats.csv`  
- **schema**：
  - `run_id`: string（仅包含启用 Intent 模块的 run）
  - `intent_label`: string（FACTOID / LIST / FILTER / AMBIGUOUS / UNKNOWN 等）
  - `count`: int（该标签作为 top1 的样本数）
  - `ratio`: float（该标签作为 top1 的比例）

该文件统计了每个启用 Intent 的 run 的 top1 意图分布，便于在正文与表格中描述 UNKNOWN / AMBIGUOUS 等类别的占比，并与 `intent_ablation_compare.json.intent_label_top1` 互相印证。

### 5. 阈值扫描结果：threshold\_sweep\_summary.csv（D）

- **位置**：`intent_workspace/artifacts/threshold_sweep_summary.csv`  
- **schema**：
  - `multi_label_threshold`: float
  - `ambiguous_margin`: float
  - `min_confidence`: float
  - `ambiguous_rate`: float
  - `multi_intent_rate`: float
  - `coverage_rate`: float
  - `n`: int
  - `intent_config_fingerprint`: string（SHA256 指纹）
  - `gold_macro_f1`: float | 空
  - `gold_accuracy`: float | 空

本任务中仅使用意图层面的 `ambiguous_rate`、`multi_intent_rate`、`coverage_rate` 与 `n`，并把 `gold_macro_f1` 与 `gold_accuracy` 的空值情况显式写入阈值分析段落；不会对缺失的任务级指标做任何臆测。

### 6. 案例集：casebook.md（E）

- **位置**：`intent_workspace/artifacts/casebook.md`  
- **结构**：
  - 分为 Clarify-applied cases、Multi-intent cases、Route-active cases、Failure/boundary cases 等小节；
  - 每个案例包含：
    - `id`
    - `Question`
    - `Intent prediction`
    - `clarification_question`、`clarification_options`
    - `final_answer`（rule\_v1 与 clarify/route 版本）
    - `EM/F1 before → after`
    - `Triggered rules`
    - 可选的 `is_multi_intent`、`is_ambiguous`、`Retrieved triples` 等字段。

本任务中所有 case study 段落均直接基于这些案例，仅做中文总结与“为什么重要”的定性解释。

### 7. 错误切片：error\_slices.md（F）

- **位置**：`intent_workspace/artifacts/error_slices.md`  
- **结构**：
  - 描述源 run（当前为 `exp_default_intent_rule_v1_real_v1`）；
  - 提供按 top1 `intent_label` 聚合的 Markdown 表格：
    - `intent_label`
    - `n`
    - `EM_avg`
    - `F1_avg`
    - `unknown_rate`

本任务在附录与正文中引用这些聚合统计，用于说明不同意图类别上的表现差异与误差模式，所有数值保持两位小数近似，不对原表做任何再计算。

### 8. 规则触发频率：rules\_trigger\_frequency.csv（G）

- **位置**：`intent_workspace/artifacts/rules_trigger_frequency.csv`  
- **schema**：
  - `rule_id`: string
  - `label`: string（规则对应的意图标签）
  - `count`: int（规则被触发的样本数）
  - `ratio`: float（规则触发比例）

该文件用于分析哪些规则主导了 Intent 判定，并支撑主文与 LaTeX 表中的规则频率统计。

### 9. fail-fast 规则与复现步骤

- **fail-fast 规则**
  - 若 A–G 任意工件缺失或解析失败：
    - 对应依赖该工件的正文段落与表格不应生成，或应显式标记为 `TODO` 并给出修复建议；
  - 若某字段在多处工件间出现矛盾（例如同一 run 的 EM 在 JSON 与 CSV 中不一致）：
    - 优先记录冲突并停止定量描述，而不是选择其中一侧当作“真值”；
  - 若关键列本身为空（如 `threshold_sweep_summary.csv` 中的 `gold_macro_f1` 与 `gold_accuracy`）：
    - 在文中只做“该列缺失”的事实性说明，不在其基础上构造任何新的指标或结论。

- **从主线 run 复现本次分析工件的高层步骤**
  1. 按 `intent_workspace/README.md` 中“主线 QA + Intent 对比实验”一节的命令，运行四个主线模式：none / rule\_v1 / rule\_v1\_route / rule\_v1\_clarify，得到对应的 `runs/exp_default_intent_*_real_v1/` 目录。
  2. 使用汇总脚本（如 `scripts/intent_ablation_compare.py`）从四个主线 run 的 `metrics.json` 与 per-sample 结果中生成 `intent_ablation_compare.json` 与 `intent_ablation_main_table.csv`。
  3. 通过 Intent 专用脚本生成意图分布与规则统计工件：
     - `intent_trigger_stats.csv`：统计 top1 intent 分布；
     - `threshold_sweep_summary.csv`：在固定配置下扫描一组阈值网格；
     - `casebook.md`：从 per-sample 结果中抽取代表性案例；
     - `error_slices.md`：按 top1 intent 聚合错误切片；
     - `rules_trigger_frequency.csv`：按 rule\_id 汇总触发次数。
  4. 最终，使用本 paper\_pack 下的中文正文、LaTeX 表格与附录文件，将上述工件转化为论文可直接引用的文本与表格。

在整个流程中，主线 run 与 intent\_workspace run 通过共享的配置与指纹工具保持一致性，而所有派生的 CSV/JSON/Markdown 工件都应被视为这些基础产物上的只读投影。本附录所列 schema 与 fail-fast 原则旨在保证：任何后续扩展实验只要遵循相同约束，就可以在不改动主线配置的前提下，持续产出可审计、可复现的 Intent 分析结果。

