## Intent 模块消融实验结果（主线四种模式）

本节基于 `intent_workspace/artifacts/intent_ablation_main_table.csv` 与 `intent_workspace/artifacts/intent_ablation_compare.json`，总结主线四种 `intent_mode`（none / rule_v1 / rule_v1_route / rule_v1_clarify）在同一配置下的表现差异。所有 run 均来自 `scripts/run_exp_baseline.py`，使用相同的合同、检索与守护策略（见 `intent_ablation_main_table.csv` 中的 `contract_variant=answer_plus_evidence_guardrail_v2`、`enforcement_policy=retry_once_if_support_lt_0.5_else_force_unknown`、`retriever_type=bm25`、`retriever_topk=10` 字段），并在 55 个样本上进行评估（见 `intent_ablation_compare.json.metrics.n`）。

本节对比结果仅针对当前离线评测子集（n=55）与冻结默认真实配置；结论为描述性统计对比，不作统计显著性或全数据集泛化推断。

### 整体 EM / F1 与 UNKNOWN 比例

从 `intent_ablation_main_table.csv` 可见，在相同数据与配置下，四种模式的整体指标大致为：

- **none（无 Intent）**：`EM ≈ 0.400`，`F1 ≈ 0.720`，`unknown_rate ≈ 0.018`。
- **rule_v1（审计-only）**：`EM ≈ 0.345`，`F1 ≈ 0.711`，`unknown_rate ≈ 0.018`。
- **rule_v1_route（路由）**：`EM ≈ 0.364`，`F1 ≈ 0.729`，`unknown_rate = 0.000`。
- **rule_v1_clarify（澄清 + 强制 UNKNOWN）**：`EM ≈ 0.364`，`F1 ≈ 0.684`，`unknown_rate ≈ 0.073`。

clarify 模式在离线评测中对 `is_ambiguous=True` 的样本强制 `final_answer=UNKNOWN`，用于避免非交互设定下的无根据回答；不等价于在线多轮澄清对话的最终效果。

这些数值在 `intent_ablation_compare.json.metrics` 与 `unknown_rate` 字段中得到了一致的印证。可以看到，在本数据集与设定下：

- 引入纯审计模式 `rule_v1` 后，F1 基本与 no-intent 持平（约 0.71–0.72），EM 略有下降（0.40 → 0.35 左右），但 UNKNOWN 比例几乎不变。
- 路由模式 `rule_v1_route` 在保持 UNKNOWN 比例为 0 的同时略微提升了 F1（约 0.729），EM 也略高于 `rule_v1`，说明在当前规模下，基于意图的检索策略调整并未显著破坏整体答案质量。
- 澄清模式 `rule_v1_clarify` 在 F1 上略低于 `rule_v1` 与 `rule_v1_route`，但 UNKNOWN 比例明显上升到约 0.073，符合“对歧义样本强制输出 UNKNOWN”的设计目标。

所有以上结论仅针对本数据集与这四组具体配置；我们不将这些现象外推到更广泛场景。

### 多意图率、歧义率与覆盖率

在启用了 Intent 模块的三种模式（`rule_v1`、`rule_v1_route`、`rule_v1_clarify`）下，`intent_ablation_main_table.csv` 与 `intent_ablation_compare.json.intent` 中给出的总体统计基本一致：

- **多意图率（multi_intent_rate）**：约为 `0.109`，即约 11% 的样本被判定为多意图；该比例在三个启用模式下保持一致。
- **歧义率（ambiguous_rate）**：约为 `0.055`，即约 5% 的样本被标记为歧义；三个启用模式下同样一致。
- **覆盖率（intent_coverage_rate 或 intent.coverage_rate）**：在启用模式下均为 `1.000`，即每个样本都得到了至少一个意图预测。

这些统计与 `intent_workspace/runs/_index/index.jsonl.key_metrics` 中的 `ambiguous_rate`、`multi_intent_rate`、`coverage_rate` 字段保持一致，说明 Intent 模块在主线实验中的启用方式与阈值设置是稳定且可审计的。

### Top1 意图分布与 UNKNOWN 标签

`intent_workspace/artifacts/intent_trigger_stats.csv` 与 `intent_ablation_compare.json.intent_label_top1` 提供了启用 Intent 时各标签的 top1 分布。以 `exp_default_intent_rule_v1_real_v1` 为例：

- UNKNOWN 作为 top1 意图的样本数为 41，占比约 `0.745`。
- AMBIGUOUS 为 top1 的样本数为 6，占比约 `0.109`。
- FACTOID、LIST、FILTER 合计占比较小（FACTOID 约 `0.073`，LIST 约 `0.055`，FILTER 约 `0.018`）。

`intent_trigger_stats.csv` 中对 `exp_default_intent_route_real_v1` 与 `exp_default_intent_clarify_real_v1` 给出了几乎相同的分布，这与 `intent_ablation_compare.json` 中三个启用模式的 `intent_label_top1` 完全一致，表明在当前配置下，路由与澄清不会改变 top1 意图的总体统计，只是改变了后续检索或答案决策。

结合 `error_slices.md` 中按 top1 intent 聚合的误差切片可以看到，UNKNOWN 类别在样本数量与平均 F1 上都相对占优，而 AMBIGUOUS 与 LIST 等类别在样本数较少的前提下平均 EM/F1 略低。这进一步说明 Intent 模块主要将高不确定性或多意图问题集中到特定标签下，为后续路由与澄清策略提供了明确的切入点。

在排版层面，主文可以仅展示按触发比例排序的 top-K top1 意图分布表（对应 `latex/intent_trigger_stats_table_topk.tex`），完整分布则放入附录表（对应 `latex/intent_trigger_stats_table_full.tex`）以便审稿人或复核者查阅。

