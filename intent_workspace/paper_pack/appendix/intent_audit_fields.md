## Intent 相关审计字段清单（intent\_audit\_fields）

本附录基于 `intent_workspace/README.md`、`intent_workspace/artifacts_schema.md`、`intent_workspace/runs/_index/index.jsonl` 以及主线汇总工件（如 `intent_workspace/artifacts/intent_ablation_compare.json`），梳理与 Intent 模块相关的审计字段，并对主线 run 与 intent\_workspace run 的审计差异进行对比说明。

### 1. 主线 KGQA run 的审计字段

主线 KGQA 实验入口为根目录的 `scripts/run_exp_baseline.py`，其每次运行会在主仓库的 `runs/<run_id>/` 下生成 `metrics.json` 等产物，并在 `metrics.json.audit` 中写入与 Intent 相关的审计字段（见 `reports/Task18_20_intent_module_summary.md` 第 6、7 节）：

- **核心审计字段（来自主线 metrics.json.audit）**
  - `config_fingerprint`：主线 KGQA 实验的整体配置指纹（包括合同、守卫策略、检索配置等），由主线的 fingerprint 工具生成。
  - `intent_module_enabled`：布尔值，指示此次 run 是否启用了 Intent 模块。
  - `intent_rules_sha256`：当启用 Intent 模块时，记录 `configs/intent_rules.yaml` 的 SHA256 指纹。
  - `intent_taxonomy_sha256`：当启用 Intent 模块时，记录 `configs/intent_taxonomy.yaml` 的 SHA256 指纹。
  - `intent_thresholds`：当启用 Intent 模块时，记录当前使用的阈值配置（multi\_label\_threshold, ambiguous\_margin, min\_confidence 等）。

- **与 Intent 结果相关的聚合统计（来自主线 metrics.json 或对比工件）**
  - `metrics.EM`、`metrics.F1`：主线 QA 任务级的 EM/F1 指标（见 `intent_ablation_compare.json.metrics`）。
  - `unknown_rate`：最终答案为 UNKNOWN 的样本比例（见 `intent_ablation_compare.json.unknown_rate`）。
  - `intent.module_enabled` / `intent.multi_intent_rate` / `intent.ambiguous_rate` / `intent.coverage_rate`：Intent 模块的整体统计（见 `intent_ablation_compare.json.intent.*`）。

这些字段共同保证：在不改变主线指标含义的前提下，可以从审计角度追踪“当前 run 是否启用 Intent 模块、使用了哪一版规则与 taxonomy、采用了怎样的阈值配置”。

### 2. intent\_workspace run 的审计字段

intent\_workspace 下的每次运行由 `intent_workspace/scripts/run_intent_exp.py` 驱动，并在 `intent_workspace/runs/<run_id>/` 中落盘六类必需文件（见 `intent_workspace/artifacts_schema.md` 与 `intent_workspace/README.md`）：

1. `repro_manifest.json`  
   - 核心审计字段：
     - `run_id`：本次运行 ID。
     - `python_version`、`platform`：环境信息。
     - `input_files_sha256`、`data_hashes`：输入数据与配置类文件的哈希。
     - `config`、`args`：实际使用的配置字典与解析后的 CLI 参数。
     - `git_commit`：当前仓库 HEAD 的 commit hash（若可获取）。
     - `config_fingerprint`：对实际生效配置（taxonomy + rules + thresholds + flags + CLI overrides）做 canonical JSON + SHA256 得到的指纹。
     - `audit_overrides`、`fingerprint_overridden`（可选）：记录 CLI 覆盖导致的指纹变更情况。

2. `config_snapshot.yaml`  
   - 核心审计字段：
     - `effective_config.defaults`：`intent_experiment_defaults.yaml` 展开的全部内容。
     - `effective_config.taxonomy`：`intent_taxonomy.yaml` 展开的全部内容。
     - `effective_config.rules`：`intent_rules.yaml` 展开的全部内容。
     - `effective_config.thresholds`：当前生效的阈值配置。
     - `effective_config.cli_overrides`：所有 CLI 覆盖条目。
     - `audit.config_fingerprint` 与 `audit.fingerprint_overridden`：与 `repro_manifest.json` 中保持一致。

3. `metrics.json`  
   - Intent 效果与覆盖统计相关字段（见 `intent_workspace/artifacts_schema.md`）：
     - `overall.macro_f1`、`overall.micro_f1`（如存在 gold labels）。
     - `overall.multi_intent_accuracy`。
     - `overall.ambiguous_rate`、`overall.multi_intent_rate`、`overall.coverage_rate`。
     - `per_label.<label>.precision/recall/f1/support`（如存在 gold labels）。
     - `rule_stats.n_samples`、`rule_stats.n_with_any_rule`。
     - `audit.config_fingerprint`、`audit.input_path`、`audit.input_hash`、`audit.git_commit`。

4. `per_sample_intent_results.jsonl`  
   - 样本级审计字段：
     - `id`、`question`。
     - `gold_intents`（如无 gold 则为 `null`）。
     - `pred_intents`：`[{label, score}]`。
     - `is_multi_intent`、`is_ambiguous`。
     - `clarification_question`、`clarification_options`。
     - `rules_fired`：`[{rule_id, label, weight}]`。
     - `thresholds_used`：记录本样本使用到的阈值组合。

5. `run.log`  
   - 至少包含输入路径与样本条数、随机种子与关键阈值、运行模式（rule\_predict / report 等）、`run_id` 与 `config_fingerprint`、总耗时等。

6. `summary.md`  
   - 面向人类审查的 3–10 行摘要，概述本次运行目的、关键指标与主要发现。

此外，`intent_workspace/runs/_index/index.jsonl` 作为跨 run 索引文件，每行记录一次成功运行的概要审计信息（见 `artifacts_schema.md` 与当前索引内容）：

- `run_id`：如 `intent_20260205_183901_default_guardrail_v2_policyR_none`。
- `datetime`：运行结束时间。
- `mode`：运行模式（当前样例为 `from_mainline`）。
- `config_fingerprint`：针对 Intent 配置生成的指纹；在与主线对接的 from\_mainline 模式中，none run 可为 `null`，启用 Intent 的 run 共享同一 fingerprint。
- `input_path`、`input_hash`：主输入数据路径及其哈希（当前样例中 `input_hash` 为空，需在未来版本中补齐以增强审计完备性）。
- `key_metrics`：至少包含 `ambiguous_rate`、`multi_intent_rate`、`coverage_rate`，已在样例中对四个 from\_mainline run 给出：  
  - none：三者均为 `0.0`；  
  - rule\_v1 / rule\_v1\_route / rule\_v1\_clarify：`ambiguous_rate ≈ 0.0545`、`multi_intent_rate ≈ 0.1091`、`coverage_rate = 1.0`。  
- `notes`：备注（当前样例均为 `from_mainline_baseline`）。

### 3. 主线 run vs intent\_workspace run 的审计对比

综合以上工件，可以看到主线 run 与 intent\_workspace run 在审计维度的分工与对齐关系：

- **主线 run（KGQA 视角）**
  - 关心的是“给定合同、守卫策略与检索配置下，整体 QA 表现与 Intent 辅助模块的交互情况”；
  - `metrics.json.audit` 中的 Intent 字段只记录“是否启用模块、使用了哪套规则/标签/阈值”，不展开 Intent 内部的样本级细节；
  - 通过 `intent_ablation_compare.json` 这样的汇总工件，将主线 run 的 EM/F1 与 UNKNOWN 比例、Intent 启用状态、意图分布等统一对比。

- **intent\_workspace run（Intent 视角）**
  - 从 Intent 模块本身的可解释性和可复现性出发，要求为每次实验记录完整的配置快照、指纹、环境信息以及 per-sample 意图预测结果；
  - `runs/_index/index.jsonl` 提供横向对比入口，`config_fingerprint` 与 `key_metrics` 则是 Intent 层面的“最小审计子集”；
  - 与主线 run 通过共享的配置文件（taxonomy/rules/thresholds）与指纹工具建立连接，但在落盘路径与命名空间上完全隔离。

在本论文的分析中，所有关于主线四个 run（`exp_default_intent_{none,rule_v1,route,clarify}_real_v1`）的 QA 指标与 Intent 统计均来自 `intent_ablation_compare.json` 与相关 CSV/JSON 工件；所有关于 Intent 内部配置、指纹与样本级行为的描述则基于 intent\_workspace 下的 artifacts 与索引文件。两者通过 `config_fingerprint` 及共享的 taxonomy/rules/thresholds 建立可审计的关联，而不在论文层面对任何一侧的配置做反向推断或修改。

