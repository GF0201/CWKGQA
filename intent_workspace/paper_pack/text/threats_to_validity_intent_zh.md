## Intent 模块的有效性与威胁（Threats to Validity）

本节基于 `intent_workspace/README.md`、`intent_workspace/runs/_index/index.jsonl`、`intent_workspace/artifacts/intent_ablation_compare.json`、`intent_workspace/artifacts/intent_trigger_stats.csv` 与 `intent_workspace/artifacts/error_slices.md` 等工件，讨论当前 Intent 模块实验结论的适用范围与可能的威胁。

### rule_v1：审计-only 模式的边界

从 `reports/Task18_20_intent_module_summary.md` 与主线脚本的设计可以看出，`intent_mode = rule_v1` 在主线中被刻意限定为“审计-only”模式：

- IntentEngine 仅用于对每条样本打标签与记录审计信息（包括意图预测、规则触发、阈值与配置指纹），相关字段被写入主线的 `metrics.json.audit` 以及 `runs/_index/index.jsonl.key_metrics`。
- `intent_ablation_main_table.csv` 显示，在 `none` 与 `rule_v1` 两种模式下，`contract_variant`、`enforcement_policy`、`retriever_type` 与 `retriever_topk` 完全一致，说明主线 QA 的合同与检索策略未因启用 Intent 模块而改变。
- `intent_ablation_compare.json` 中 `intent.module_enabled` 与 `intent.multi_intent_rate`、`intent.ambiguous_rate` 等字段仅作为额外审计信号出现，不参与回答生成的决策过程。

因此，在解释 `rule_v1` 模式下的结果时，应将其视为“对主线行为的结构化观测与记录”，而非“改变主线行为后得到的新系统”。这一点对于避免“偷改主实验”的质疑尤为关键。

### route / clarify：行为改变模式的适用范围

与 `rule_v1` 不同，`rule_v1_route` 与 `rule_v1_clarify` 明确属于行为改变（behavior-changing）模式：

- 在 `rule_v1_route` 中，检索策略会根据预测意图进行调整，例如对多事实类问题提升 top_k，对部分意图类别采用不同的检索配置（具体策略见 `reports/Task18_20_intent_module_summary.md` 中的路由描述）。这意味着，尽管合同与 enforcement policy 保持不变，主线的证据集合与最终答案可能发生系统性变化。
- 在 `rule_v1_clarify` 中，当 IntentEngine 将样本标记为歧义时，系统在离线评测中会将最终答案强制设置为 `UNKNOWN`（见 `casebook.md` Clarify-applied 小节与 `intent_ablation_compare.json.unknown_rate` 字段）。该策略直接改变了答案分布与 EM/F1 指标。

因此，基于 route/clarify 模式得到的结果应被明确标注为“实验性配置”或“对比实验”，适合作为论文中的补充分析，但不应与主线 `none` / `rule_v1` 模式混为一谈。`intent_ablation_main_table.csv.intent_mode` 与 `_index/index.jsonl.mode/notes` 字段提供了区分这些 run 的必要信息。

### 数据规模与标签分布的局限

`intent_ablation_compare.json.metrics.n` 与 `threshold_sweep_summary.csv.n` 均表明，本次主线对比实验与阈值扫描均基于约 55 个样本。在这一规模下：

- `intent_trigger_stats.csv` 显示 UNKNOWN 作为 top1 意图的样本约为 41 条（占比约 0.745），AMBIGUOUS 约为 6 条（占比约 0.109），其他标签样本较少。这种分布说明：当前实验更偏向于验证“规则在发现未知或模糊问题上的能力”，而非在大量多样化意图上做精细评估。
- `error_slices.md` 中的切片表明，不同意图类别的平均 EM/F1 存在明显差异：例如 AMBIGUOUS 类别样本数仅为 6 条，平均 EM 与 F1 略低，而 FACTOID、UNKNOWN 类别在更少或更多样本上表现更好。这些现象在小样本条件下可能受到偶然性和数据偏采样的显著影响。

因此，论文在引用本次实验的定量结论时，应反复强调“基于当前 55 条样本与特定数据集”的限定条件，避免将结果简单推广到不同领域或更大规模的真实流量场景。

本节对比结果仅针对当前离线评测子集（n=55）与冻结默认真实配置；结论为描述性统计对比，不作统计显著性或全数据集泛化推断。

### 阈值与配置指纹的一致性假设

`threshold_sweep_summary.csv` 为不同的 `(multi_label_threshold, ambiguous_margin, min_confidence)` 组合记录了 `intent_config_fingerprint`，而 `runs/_index/index.jsonl` 为主线四个 run 记录了单独的 `config_fingerprint`。目前的工件中并未显式声明某一行 sweep 的 fingerprint 与主线 run 的 fingerprint 完全相同，这意味着：

- 我们可以使用 sweep 表来分析“在同一规则体系下，阈值变化如何影响 ambiguous_rate 与 multi_intent_rate”，但不能在未进一步比对指纹的前提下声称“主线 run 的阈值等于某一行 sweep 配置”。
- 若后续需要在论文中给出“推荐阈值 == 主线线上配置”的强结论，应增加一次专门的指纹对齐审计，将 `_index/index.jsonl.config_fingerprint` 与 `threshold_sweep_summary.csv.intent_config_fingerprint` 逐一比对，并将结果写入新的审计工件。

在当前材料下，本论文仅在“阈值敏感性分析”层面使用 sweep 结果，并将主线配置视为由 `config_snapshot.yaml` 与相关指纹唯一确定的黑箱，不作反向推测。

### 模块扩展与未来工作

`reports/Task18_20_intent_module_summary.md` 提到，IntentEngine 已支持与可训练模型（如 TF-IDF + Logistic Regression）进行融合，并在 `intent_workspace/artifacts/intent_training_manifest.json` 中记录了模型训练的审计信息。由于本次主线对比与阈值扫描主要基于规则通道，尚未系统评估融合模型在多意图与歧义识别上的增益，相关结论不在本论文当前范围之内。

未来若要扩展到更复杂的模型与更大规模的数据，需要：

- 在现有审计字段基础上，进一步细化模型版本、训练数据哈希与推理配置的记录方式；
- 在新的实验中复用 `intent_ablation_compare.json` 与 `threshold_sweep_summary.csv` 的结构，以便在规则与模型融合的场景下保持可比性；
- 针对高歧义与多意图样本继续扩充 `casebook.md` 与 `error_slices.md`，用于分析模型与规则在困难样本上的互补关系。

综上，当前 Intent 模块的实验结论在小样本、单一数据集与规则主导的前提下是自洽且可审计的，但在推广到更广泛应用场景时，需要特别注意模式边界（审计-only vs 行为改变）、数据规模、标签分布与配置指纹一致性等多方面的有效性威胁。

