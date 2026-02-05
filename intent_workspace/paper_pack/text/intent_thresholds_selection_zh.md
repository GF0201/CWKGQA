## Intent 阈值选择与指标折中

本节基于 `intent_workspace/artifacts/threshold_sweep_summary.csv` 与 `intent_workspace/runs/_index/index.jsonl`，分析 Intent 模块在多意图与歧义判定上的阈值扫描结果，并讨论在保持覆盖率不变的前提下，如何在歧义率与多意图率之间进行折中。由于当前 sweep 结果中 `gold_macro_f1` 与 `gold_accuracy` 列为空，我们只基于意图层面的统计与配置指纹进行分析，不对任务级指标做任何推断。

### 阈值搜索空间与审计指纹

`threshold_sweep_summary.csv` 覆盖了一个由三个超参数张成的网格：

- 多标签阈值 `multi_label_threshold` 取值约为 `0.4`、`0.6`、`0.8`。
- 歧义边界 `ambiguous_margin` 取值约为 `0.10`、`0.15`、`0.20`。
- 最小置信度 `min_confidence` 取值约为 `0.30`、`0.40`、`0.50`。

对于每一组阈值组合，文件记录了：

- `ambiguous_rate`：被判定为歧义的样本比例；
- `multi_intent_rate`：被判定为多意图的样本比例；
- `coverage_rate`：存在至少一个意图预测的样本比例（在所有行中均约为 `1.0`）；
- `n`：样本数（与主线实验一致，约为 `55`）；
- `intent_config_fingerprint`：对应配置的 SHA256 指纹。

这些指纹可以与 `runs/_index/index.jsonl` 中的 `config_fingerprint` 一起，用于审计不同实验或阈值组合是否在同一配置族内。本次整理不尝试推导或修改任何现有指纹，只使用 `intent_config_fingerprint` 作为“阈值组合已落盘”的证据。

### 歧义率与多意图率的折中

在当前 sweep 结果中，`multi_intent_rate` 在所有配置下基本保持在约 `0.109`，说明多意图的判定主要受 `multi_label_threshold` 控制，而在给定的取值范围内，多意图比例相对稳定。相比之下，`ambiguous_rate` 对 `ambiguous_margin` 更为敏感：

- 当 `multi_label_threshold` 与 `min_confidence` 固定，而 `ambiguous_margin` 从约 `0.10` 提升到约 `0.20` 时，`ambiguous_rate` 从约 `0.055` 上升到约 `0.109`，即歧义样本比例几乎翻倍；
- 在相同 `ambiguous_margin` 下，调整 `min_confidence`（如从 `0.30` 到 `0.50`）对 `ambiguous_rate` 与 `multi_intent_rate` 的影响较小，整体统计基本保持在上述两个水平附近。

这表明，在当前数据与规则体系下，`ambiguous_margin` 是控制歧义敏感度的主要旋钮：较小的边界会将更多样本视为“可直接回答”，而较大的边界则更保守地将 borderline 样本归为歧义。

### 与主线实验的一致性与限度

主线四个 run 的整体 `ambiguous_rate` 与 `multi_intent_rate`（见 `intent_ablation_compare.json.intent` 与 `_index/index.jsonl.key_metrics`）大致落在 `threshold_sweep_summary.csv` 网格覆盖的范围内，说明 sweep 实验与主线配置处于同一量级的阈值区域。然而，由于 index 中的 `config_fingerprint` 与 sweep 表格中的 `intent_config_fingerprint` 之间并未被显式标记为相等，本次整理不声称“主线实验的阈值即为某一行 sweep 配置”，而是：

- 将 sweep 结果视为对 Intent 模块在一组相邻阈值上的敏感性分析；
- 强调在 `coverage_rate ≈ 1.0` 与 `multi_intent_rate ≈ 0.109` 基本不变的前提下，仅通过调整 `ambiguous_margin` 即可在 `ambiguous_rate ≈ 0.055` 与 `≈ 0.109` 之间进行折中；
- 保留主线实际使用阈值配置由 `config_snapshot.yaml` 与相关指纹唯一确定的事实，不在论文中重写或改动该配置。

若未来需要基于任务级指标（例如 QA 的 EM/F1）进一步优化阈值，建议扩展 `threshold_sweep_summary.csv`，补齐 `gold_macro_f1` 与 `gold_accuracy` 字段，并基于新的 sweep 结果更新本节分析。在当前数据缺失的情况下，我们刻意避免对任务级表现做任何定量推断。

### 最终阈值状态

本次阈值 sweep 结果仅用于离线分析与方法比较，默认线上/主线配置仍保留为原始阈值设置；本文其他实验（包括主线四种 `intent_mode` 消融）均基于冻结的默认真实配置运行。我们未将 sweep 中的任何一行阈值组合写回 `intent_workspace/configs/intent_rules.yaml`，也不在本文中声称主线 run 的 `config_fingerprint` 与 `threshold_sweep_summary.csv.intent_config_fingerprint` 中的某一值完全相同。

