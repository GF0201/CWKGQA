### 意图模块阶段性汇报（Task 18–20）

本报告总结了当前阶段围绕意图识别（多意图 / 歧义 / 澄清）模块的 10 个关键任务及完成情况，覆盖：独立工作区、规则引擎、主流水线集成、消融对比以及可训练模型扩展。

---

### 1. 创建独立的 intent_workspace 工作区

- 在项目根下新增 `intent_workspace/`，与现有 KGQA 主流水线的 `runs/`、`artifacts/` 彻底隔离。
- 编写 `intent_workspace/README.md` 和 `intent_workspace/artifacts_schema.md`，明确：
  - 目录用途、run 产物规范（A–F 六类文件）、命名规范（`intent_<YYYYMMDD_HHMMSS>_<tag>`）；
  - `repro_manifest.json`、`config_snapshot.yaml`、`metrics.json`、`per_sample_intent_results.jsonl`、`run.log`、`summary.md` 的字段要求；
  - runs `_index/index.jsonl` 的索引字段与审计要求（run_id、config_fingerprint、key_metrics 等）。

**结果**：完成一个与主线解耦、具备清晰审计规范的意图实验工作区，为后续所有 Intent 实验提供统一落盘约束。

---

### 2. 设计与实现 Intent 配置体系（taxonomy + rules）

- 在全局 `configs/` 下新增：
  - `intent_taxonomy.yaml`：定义意图标签（FACTOID / LIST / FILTER / COMPARISON / PROCEDURE / MULTI_FACT / AMBIGUOUS / UNKNOWN），包括：
    - `name`、`definition`、`examples`、`negative_examples`。
  - `intent_rules.yaml`：定义规则与判定超参：
    - `thresholds`: `multi_label_threshold`、`ambiguous_margin`、`min_confidence`；
    - `conflict_matrix`: 例如 FACTOID vs COMPARISON、LIST vs FACTOID 等冲突对；
    - `clarification_templates`: 冲突对和通用的澄清问句模板；
    - `rules`: 为各意图配置关键词模式、权重。
- 在 `intent_workspace/configs/` 下补充实验默认配置：
  - `intent_experiment_defaults.yaml`：seed、默认输入路径、输出基础目录、thresholds、report.index_path 等。

**结果**：完成可解释、可扩展的意图标签与规则配置体系，为规则推理与审计提供统一源头配置。

---

### 3. 实现 IntentEngine v1（纯规则，多标签 + 歧义判定）

- 在 `src/intent/intent_engine.py` 实现 `IntentEngine`：
  - `predict(question: str)` 返回：
    - `intents`: `[{label, score, evidence_rules_triggered}]`（score 为 0..1 归一化分数）；
    - `is_multi_intent`、`is_ambiguous`；
    - `clarification_question`、`clarification_options`；
  - 规则来源：`configs/intent_rules.yaml` 中的 `keywords/regex/patterns/weight`。
- 实现多意图与歧义判定：
  - 多意图：归一化后分数 ≥ `multi_label_threshold` 的标签数 ≥ 2；
  - 歧义：满足任一条件：
    - `top1 - top2 <= ambiguous_margin`；
    - `top1 < min_confidence`；
    - 命中 `conflict_matrix` 且分差小。
- 澄清问题生成：
  - 优先根据 top2 标签查找 `<A>_vs_<B>` 模板，否则退回 `generic` 模板；
  - 输出澄清问句与候选意图选项。
- 审计接口 `get_audit_info()`：
  - 返回 `rules_version_sha`、`taxonomy_sha256`、`thresholds`、`config_fingerprint_intent` 等信息。

**结果**：得到一个无外部 LLM 依赖、完全可解释的 IntentEngine v1，可单独运行并输出 per-question 结构化意图信息。

---

### 4. intent_workspace 统一入口与 per-run 产物（run_intent_exp）

- 在 `intent_workspace/scripts/run_intent_exp.py` 实现统一入口，支持：
  - `--mode rule_predict`：主路径；
  - `--input`：默认 `datasets/domain_main_qa/test.jsonl`；
  - `--run_id`：未显式提供时自动生成 `intent_<timestamp>_rule_v1`；
  - `--config`：默认 `intent_workspace/configs/intent_experiment_defaults.yaml`。
- rule_predict 模式下：
  - 加载 defaults + taxonomy + rules，构造 “effective_config”，生成 canonical JSON 与 `config_fingerprint`；
  - 调用 `intent_workspace.src.intent_engine.run_rule_predict`，得到：
    - `metrics`（overall + rule_stats + audit）；
    - `per_sample_intent_results.jsonl`（含 gold_intents/pred_intents/is_multi_intent/is_ambiguous/clarification_*/rules_fired/thresholds_used）；
    - `config_snapshot`（effective_config + audit）。
  - 写出 6 大必需文件：
    - `repro_manifest.json`（基于 `core.write_repro_manifest`，补充 `config_fingerprint`、`git_commit` 等）；
    - `config_snapshot.yaml`；
    - `metrics.json`；
    - `per_sample_intent_results.jsonl`；
    - `run.log`；
    - `summary.md`（人类可读摘要）。
  - 末尾集中校验 6 个文件是否存在，缺失则提示并 exit non-zero。
- 维护索引：
  - 在 `intent_workspace/runs/_index/index.jsonl` 追加：
    - `run_id`、`datetime`、`mode`、`config_fingerprint`、`input_path/input_hash`；
    - `key_metrics`: `macro_f1`、`ambiguous_rate`、`multi_intent_rate`。

**结果**：intent_workspace 已有完整可审计的 run 生命周期，从 CLI 参数到每个 run 的文件集合和索引信息均有记录。

---

### 5. intent_workspace 辅助脚本（fingerprint + smoke + report）

- `intent_workspace/scripts/compute_config_fingerprint.py`：
  - 读取 `intent_experiment_defaults.yaml` + `intent_taxonomy.yaml` + `intent_rules.yaml`；
  - 输出 canonical JSON 的 SHA256 指纹至 `intent_workspace/artifacts/intent_default_config_fingerprint.json`。
- `intent_workspace/scripts/intent_smoke_test.py`：
  - 以 defaults 中的 input 为样本集，调用 `run_rule_predict`；
  - 在 `intent_workspace/runs/intent_smoke_*` 下写出 `metrics.json`、`per_sample_intent_results.jsonl`、`config_snapshot.yaml`、`run.log`；
  - 用于快速验证 intent_workspace 内部代码与配置连通性。
- `intent_workspace/scripts/intent_report.py`：
  - 使用全局 `IntentEngine` 跑一遍 defaults input；
  - 在 `intent_workspace/runs/<run_id>/intent_report.json` 中统计：
    - 各意图 top1 占比、多意图/歧义占比、规则触发频率；
    - 附带 `intent_audit` 字段。

**结果**：为 intent 工作区提供指纹生成、自测与报告三类实用工具，便于持续集成和人工审查。

---

### 6. 主流水线中接入 IntentEngine（基础集成）

- 在 `scripts/run_exp_baseline.py` 中：
  - 引入 `IntentEngine`，增加参数 `--intent_mode`：
    - `none`：关闭意图模块；
    - `rule_v1`：仅打标，不改变主流程行为；
  - 在 `run_experiment()` 中：
    - 若 intent_enabled，则对每个 question 调用 `IntentEngine.predict`；
    - 在 per-sample 中新增：
      - `intent_pred`：全结构输出；
      - `intent_audit`：规则版本与阈值审计信息。
  - 在 `metrics.json.audit` 中新增 intent 相关字段：
    - `intent_module_enabled`；
    - `intent_rules_sha256`、`intent_taxonomy_sha256`、`intent_thresholds`。

**结果**：主线 baseline 可以在不改变答案行为的前提下，记录每条样本的意图预测及审计信息，为后续路由和消融打下基础。

---

### 7. 路由与澄清模式（四种运行模式）

- 扩展 `--intent_mode` 选项为：`none` / `rule_v1` / `rule_v1_route` / `rule_v1_clarify`；
- 在 `run_experiment()` 中按模式实现：
  - **路由（rule_v1_route / rule_v1_clarify）**：
    - FACTOID / LIST / FILTER / COMPARISON / PROCEDURE：
      - 使用 `retriever_type="bm25"`，`top_k >= 10`；
    - MULTI_FACT（多意图）：
      - 自动放大 `top_k`（至少为默认 K 的 2 倍），提高覆盖率；
    - 当前版本不改变合同类型（contract_variant 仍由 CLI 控制），重点验证“意图感知检索策略”的可行性。
  - **澄清模式（rule_v1_clarify）**：
    - 若 `IntentEngine` 标记 `is_ambiguous=True`：
      - 在离线评测场景中，将 `final_answer` 强制设置为 `UNKNOWN`；
      - 保留 `answer_before_clarify` 与 `clarify_applied=True`，并基于最终答案重新计算 EM/F1。
- 在 `metrics.json.audit` 中补充全局 Intent 统计：
  - 自 per-sample 推导：
    - `intent_multi_intent_rate`；
    - `intent_ambiguous_rate`；
    - `intent_coverage_rate`（存在非空 `intents` 的样本比例）。

**结果**：主流水线支持四种实验模式（no-intent / rule_v1 / route / clarify），并能在审计层面看到路由/澄清对 unknown_rate 与意图分布的影响。

---

### 8. 实验对比工件：intent_ablation_compare.json

- 新增脚本 `scripts/intent_ablation_compare.py`：
  - 参数：`--runs <run_id1> <run_id2> ...`；
  - 对每个 run 读取：
    - `runs/<run_id>/metrics.json`；
    - `runs/<run_id>/artifacts/per_sample_results.jsonl`。
  - 输出到 `artifacts/intent_ablation_compare.json`，结构为：
    - 每个 run 的：
      - `metrics`: `{n, EM, F1}`；
      - `unknown_rate`：final_answer/prediction 为 `UNKNOWN` 的比例；
      - `intent.module_enabled` / `multi_intent_rate` / `ambiguous_rate` / `coverage_rate`；
      - `intent_label_top1`：各 top1 意图标签的 count / ratio；
      - 以及 `ablation`、`contract_variant`、`enforcement_policy` 等上下文信息。

**结果**：支持在一个 JSON 文件中对比 no-intent / intent-rule-v1 / route / clarify 多个 run 的关键指标与意图分布，为撰写实验分析报告提供直接输入。

---

### 9. 可训练 Intent 模型 v2（TF-IDF + LogisticRegression）

- 训练脚本 `intent_workspace/scripts/train_intent_model.py`：
  - 期望数据：
    - `intent_workspace/data/intent_labels_gold.jsonl`；
    - `intent_workspace/data/intent_labels_silver.jsonl`；
  - 使用 `TfidfVectorizer(max_features=20000, ngram_range=(1,2))` + `OneVsRest(LogisticRegression)`：
    - 固定 `random_state=42`；
    - 将 `labels` 进行多标签二值化；
    - 模型训练完成后，写出：
      - `intent_workspace/artifacts/intent_vectorizer.pkl`；
      - `intent_workspace/artifacts/intent_model.pkl`；
      - `intent_workspace/artifacts/intent_training_manifest.json`（包括 label 顺序、样本数、数据哈希、sklearn 版本等）。
- 在 `IntentEngine` 中启用融合推理：
  - `__init__(use_model: bool = False, model_dir: Path | None = None)`：
    - 若 `use_model=True`，在 `model_dir`（默认 `intent_workspace/artifacts`）中尝试加载 vectorizer、model 与 manifest；
  - 在 `predict()` 中：
    - 先用规则得到 `raw_scores`；
    - 若模型可用，则计算 `model_scores`（decision_function + sigmoid）；
    - 使用 `alpha`（配置中 `model_fusion.alpha_rule`，默认 0.5）融合：
      - `score_final = alpha * rule + (1 - alpha) * model`；
    - 剩余逻辑（多意图/歧义判定、澄清生成）保持基于 fused_scores。
- `get_audit_info()` 中增加 `model_dir` 字段，用于审计模型来源与版本。

**结果**：在规则框架基础上，增加了一个可训练、审计友好的 Intent 模型通道，可通过配置开关与权重 alpha 调整规则/模型的融合程度。

---

### 10. 整体验收与后续建议

- **可审计性**：
  - 每次 intent_workspace run 必须生成完整 A–F 文件，并写入 `_index/index.jsonl`；
  - 主流水线 run 的 `metrics.json.audit` 中，整合了 KGQA 配置指纹 + Intent 配置/模型指纹与统计；
  - `intent_ablation_compare.json` 方便多 run 对比审查。
- **可复现性**：
  - `repro_manifest.json` 和 `intent_training_manifest.json` 记录了环境（Python/requirements）、输入文件 hash、训练随机种子等；
  - default config 与 intent config 均有单独 fingerprint 工具。
- **可扩展性**：
  - IntentEngine 支持规则与模型并存，且通过 YAML 配置控制阈值与融合权重；
  - 工作区下脚本结构清晰（run_intent_exp/train_intent_model/intent_report/intent_smoke_test），便于进一步添加模型版本或规则版本。

**建议下一步工作**：

- 补充少量高质量 gold 标注，验证并微调 TF-IDF 模型与规则的融合策略；
- 针对典型疑难问题（高歧义、多意图）整理 case study，结合 `intent_ablation_compare.json` 做更细粒度分析；
- 将常用的 4 种 baseline 模式（no-intent / rule_v1 / route / clarify）固化为批量运行脚本，简化实验流水线。

