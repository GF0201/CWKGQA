## Intent 模块方法与审计设计

本节基于 `intent_workspace/README.md`、`intent_workspace/runs/_index/index.jsonl`、`configs/intent_rules.yaml`、`configs/intent_taxonomy.yaml` 以及 `intent_workspace/artifacts/threshold_sweep_summary.csv` 等工件，总结 IntentEngine v1 的实现方式及其审计字段设计。所有字段与数值均可在 `intent_workspace/paper_pack/text/source_files_manifest.md` 中追溯到具体文件与列名。

### IntentEngine v1：规则驱动的多标签 + 歧义检测

IntentEngine v1 是一个**纯规则、无外部模型依赖**的意图识别组件，按照 `intent_workspace/README.md` 与 `reports/Task18_20_intent_module_summary.md` 的描述，其核心特征包括：

- **多标签规则推理**：从 `configs/intent_rules.yaml` 读取规则集合与阈值配置，对每个输入问题返回一组候选意图 `[{label, score}]`，其中 `score` 为归一化后的 0–1 分数（见 `reports/Task18_20_intent_module_summary.md` 对 `predict()` 接口的说明）。
- **多意图判定**：若得分不低于 `multi_label_threshold` 的标签数量不少于 2，则判定为多意图样本，对应的总体多意图比例在主线四个实验中约为 0.109（见 `threshold_sweep_summary.csv.multi_intent_rate` 及 `intent_ablation_compare.json.intent.multi_intent_rate`）。
- **歧义检测**：综合 `ambiguous_margin` 和 `min_confidence` 两个阈值，当 top1 与 top2 分数差距较小或整体置信度偏低时，将样本标记为歧义；在主线实验的基线阈值附近，整体歧义率约为 0.055 或 0.109（见 `threshold_sweep_summary.csv.ambiguous_rate`）。
- **澄清问题生成**：当检测到冲突意图（例如 LIST 与 AMBIGUOUS）时，组件根据 `intent_rules.yaml` 中的 `clarification_templates` 构造澄清问题与候选选项，并在澄清模式下用于离线强制 UNKNOWN 的分析（具体案例见 `casebook.md`）。

### 四种 intent_mode 运行模式

根目录脚本 `scripts/run_exp_baseline.py` 支持四种运行模式（见 `intent_workspace/README.md` 与 `reports/Task18_20_intent_module_summary.md`）：

1. **`intent_mode = none`**：完全关闭 Intent 模块，仅运行主线 KGQA。与意图相关的字段在对比工件中为空或标记为未启用（例如 `intent_workspace/artifacts/intent_ablation_compare.json` 中 `intent.module_enabled=false`）。
2. **`intent_mode = rule_v1`**：仅对每个样本进行规则打标与审计，不改动检索与回答行为。主线 run `exp_default_intent_rule_v1_real_v1` 的配置可在 `intent_ablation_main_table.csv` 与 `_index/index.jsonl` 中看到，其中 `contract_variant`、`enforcement_policy`、`retriever_type=bm25`、`retriever_topk=10` 与其他模式保持一致。
3. **`intent_mode = rule_v1_route`**：在 `rule_v1` 的基础上，根据预测意图调整检索策略（例如对多事实类问题提高检索的 top_k），但不改变合同类型；其 run `exp_default_intent_route_real_v1` 与主线配置的一致性同样由 `intent_ablation_main_table.csv` 及 `_index/index.jsonl` 中的上下文字段保证。
4. **`intent_mode = rule_v1_clarify`**：在路由的基础上，对被判定为歧义的问题在离线评测中强制输出 `UNKNOWN`，并在对比工件中单独统计澄清前后的 EM/F1 变化（见 `casebook.md` 中 Clarify-applied 小节以及 `intent_ablation_compare.json` 中的 `unknown_rate` 字段）。

在四种模式下，主线脚本始终通过 CLI 参数显式设置 `--contract_variant`、`--enforcement_policy`、`--retriever_type` 和 `--top_k`，并在对比工件 `intent_ablation_main_table.csv` 中保留这些字段，用于证明四组实验仅在 `intent_mode` 这一维度上发生变化。

### 审计与指纹字段

Intent 模块的设计目标之一是**可审计与可复现**。按照 `intent_workspace/README.md` 与 `_index/index.jsonl` 的约定，每次主线或 intent_workspace 运行都需要写出一套完整的审计字段：

- **配置指纹（config_fingerprint）**：在 intent_workspace 中，`compute_config_fingerprint.py` 将实际生效的 taxonomy、rules 与 thresholds 展开为 canonical JSON，并写入 `repro_manifest.json.config_fingerprint`、`metrics.json.audit.config_fingerprint` 以及 `runs/_index/index.jsonl.config_fingerprint`。在阈值扫描实验中，`threshold_sweep_summary.csv.intent_config_fingerprint` 为每个阈值组合单独记录了一个 SHA256 指纹，用于锁定当时的配置。
- **意图统计审计（key_metrics）**：`runs/_index/index.jsonl.key_metrics` 至少包含 `ambiguous_rate`、`multi_intent_rate` 与 `coverage_rate` 三个字段，用于快速比较不同 run 的整体意图分布，与 `intent_ablation_compare.json.intent` 与 `intent_trigger_stats.csv` 中的统计互相印证。
- **主线审计字段**：主线 KGQA 的 `metrics.json.audit` 中合并了 KGQA 配置指纹与 Intent 模块的指纹（见 `reports/Task18_20_intent_module_summary.md` 中对审计字段的列举），保证对比实验不会在“隐形更改配置”的前提下进行。

在本次论文材料整理中，我们只引用已有工件中的哈希值和统计字段，不重新生成任何指纹，也不修改任何环境变量或密钥。若后续需要补充环境变量的来源，只会在附录中以 `ENV:VAR_NAME` 的形式提及变量名，而不会记录其具体取值。

