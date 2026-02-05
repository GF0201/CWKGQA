## 目录用途

`intent_workspace/` 用于承载 **意图识别（多意图 / 歧义 / 澄清）** 相关的所有代码、配置、实验运行及审计产物，和现有 KGQA 主流水线的 `artifacts/`、`runs/` 完全隔离，保证：

- **可审计**：每次运行都能完整追踪数据与配置来源；
- **可复现**：通过 `repro_manifest.json` 与 `config_snapshot.yaml` 即可重放同一实验；
- **可对比**：通过 `runs/_index/index.jsonl` 快速汇总与对比多次实验结果。

## 目录结构

- `configs/`
  - `intent_taxonomy.yaml`：意图标签体系定义（标签、含义、层级等）；
  - `intent_rules.yaml`：规则引擎配置（规则 ID、匹配模式、权重、目标标签等）；
  - `intent_experiment_defaults.yaml`：实验默认配置（随机种子、输入路径、阈值、规则/标签文件路径等）。
- `src/`
  - `intent_engine.py`：意图识别核心逻辑（规则/模型推理、多意图与歧义判定、指标聚合）；
  - `utils.py`（可选）：通用工具函数。
- `scripts/`
  - `run_intent_exp.py`：统一入口，支持 `--mode rule_predict` / `--mode report` 等；
  - `intent_smoke_test.py`：对 taxonomy / rules / 简单样例进行自测的脚本；
  - `intent_report.py`：从 `runs/_index/index.jsonl` 生成统计报告或人类可读总结；
  - `compute_config_fingerprint.py`：对“实际生效配置”生成 canonical JSON + SHA256 指纹。
- `runs/`
  - `<run_id>/`：单次运行的完整产物目录（见下文“每次运行必需产物”）；
  - `_index/index.jsonl`：所有 run 的索引文件。
- `artifacts_schema.md`：规约每次 run 必须产出的文件及关键字段。

## run_id 命名规范

- 统一格式：`intent_<YYYYMMDD_HHMMSS>_<short_tag>`
- 例：`intent_20260205_153000_rule_v1`
- 所有脚本生成的输出 **只允许** 写入：`intent_workspace/runs/<run_id>/` 下（索引文件除外）。

## 每次运行必需产物（A–F）

每个 `run_id` 目录下必须落盘以下文件，否则视为 **失败运行**，主脚本会以非零退出码结束：

1. `repro_manifest.json`  
   - 记录环境与可复现信息，包括：
     - `python_version` / `platform`；
     - `git_commit`（若可获取）；
     - `input_files_sha256` 与 `data_hashes`（输入数据与配置文件的哈希）；
     - `config_fingerprint`（见下节）；
     - 完整命令行参数与随机种子等。
2. `config_snapshot.yaml`  
   - 将本次 **实际生效的所有配置**（taxonomy + rules + thresholds + flags + CLI 覆盖）展开后完整写出。
3. `metrics.json`  
   - 总体意图指标：
     - `overall.macro_f1` / `overall.micro_f1`；
     - `overall.multi_intent_accuracy`；
     - `overall.ambiguous_rate`；
     - `overall.multi_intent_rate`；
   - 分标签指标：
     - `per_label.<label>.precision` / `recall` / `f1` / `support`；
   - 规则覆盖统计（rule-only 时仍需给出 coverage / trigger 统计）；
   - 审计字段：
     - `audit.config_fingerprint`；
     - `audit.input_path` / `audit.input_hash`；
     - `audit.git_commit`（若可获取）。
4. `per_sample_intent_results.jsonl`  
   - 每行至少包含：
     - `id`, `question`；
     - `gold_intents`（如无 gold 则为 `null`）；
     - `pred_intents`: `[{label, score}]`；
     - `is_multi_intent`, `is_ambiguous`；
     - `clarification_question`, `clarification_options`；
     - `rules_fired`: `[{rule_id, label, weight}]`；
     - `thresholds_used`。
5. `run.log`  
   - 通过 `DualLogger` 同步写入控制台与文件，至少记录：
     - 输入数据路径与样本条数；
     - 关键阈值与随机种子；
     - 运行模式（rule_predict / report / …）；
     - 开始与结束时间、总耗时；
     - 配置指纹与 run_id。
6. `summary.md`  
   - 3–10 行人类可读摘要，推荐内容：
     - 本次运行目的与配置 tag；
     - 关键结果（macro/micro F1、多意图比率、歧义检出率等）；
     - 主要发现与问题；
     - 与历史 run 的简单对比结论（可选）。

主脚本在运行结束后，会**统一检查以上文件是否存在**；如缺失任何一个，立即在控制台提示缺失项，并以非零退出码结束。

## 配置指纹（Config Fingerprint）

- 对 `intent_workspace/configs/` 下 **实际生效配置**（包括 YAML + CLI overrides）构造一个 Python 字典：
  - 包含展开后的 taxonomy / rules / thresholds / flags 等；
  - 将该字典转为 **canonical JSON**（键排序、禁用多余空格）；
  - 对 canonical JSON 计算 `SHA256`，得到 `fingerprint_sha256`。
- 指纹写入位置：
  - `repro_manifest.json.config_fingerprint`；
  - `metrics.json.audit.config_fingerprint`；
  - `runs/_index/index.jsonl` 中的 `config_fingerprint` 字段。
- 若存在 CLI 覆盖参数：
  - 在 `config_snapshot.yaml` 与 `repro_manifest.json` 中附加 `audit_overrides` 列表；
  - 推荐同时记录 `fingerprint_overridden`（目前实现中保留该字段接口，若无 overrides 则与 `config_fingerprint` 相同）。

## 数据与标签策略

- 默认输入数据：
  - `datasets/domain_main_qa/test.jsonl`（问题 + gold 答案/证据，用于无标签场景下的 rule-only 分析）。
- 如需显式意图 gold labels：
  - 新建：
    - `intent_workspace/data/intent_labels_gold.jsonl`；或
    - `intent_workspace/data/intent_labels_silver.jsonl`（规则弱监督）；
  - 必须在文件中 **显式标注 gold/silver**，不得混用或混淆；
  - 所有 label 数据文件都会被 hash 并写入 `repro_manifest.json.data_hashes`。

## 实验入口与运行方式

- 推荐通过根目录脚本：
  - `python scripts/run_intent_exp.py --mode rule_predict --config intent_workspace/configs/intent_experiment_defaults.yaml`
- 关键参数：
  - `--mode`：`rule_predict` / `report` / （可选）`train_model` / `eval_model`；
  - `--input`：输入数据路径，默认 `datasets/domain_main_qa/test.jsonl`；
  - `--run_id`：`auto` 或显式提供的 run_id；
  - `--config`：默认配置 YAML 路径。
- 无论以何种方式调用，只要进行一次完整的 `rule_predict` 流程：
  - 所有必需文件（A–F）都会写入 `intent_workspace/runs/<run_id>/`；
  - 并自动将本次运行的信息追加写入 `runs/_index/index.jsonl`。

## 主线 QA + Intent 对比实验（P0）

主线 KGQA 实验入口为根目录下的 `scripts/run_exp_baseline.py`，已内置 `--intent_mode` 参数用于对比 4 种模式：

- `--intent_mode none`：关闭 Intent 模块，仅跑主线 QA；
- `--intent_mode rule_v1`：仅做规则打标与审计，不改变 QA 行为；
- `--intent_mode rule_v1_route`：根据意图路由检索配置（如切换 BM25 / 调整 top_k）；
- `--intent_mode rule_v1_clarify`：在 route 基础上，遇到歧义样本时强制输出 `UNKNOWN`（离线澄清）。

典型命令示例（从仓库根目录运行）：

- 冒烟测试（不调用真实模型，仅验证流水线连通性）：
  - `python scripts/run_exp_baseline.py --mock --intent_mode rule_v1 --output_id exp_intent_rule_v1_smoke`
- 真实对比实验（需配置好 `MKEAI_API_KEY` 或 `OPENAI_API_KEY`）：
  - `python scripts/run_exp_baseline.py --seed 42 --contract_variant answer_plus_evidence_guardrail_v2 --enforcement_policy retry_once_if_support_lt_0.5_else_force_unknown --retriever_type bm25 --top_k 10 --intent_mode none          --output_id exp_default_intent_none_real_v1`
  - `python scripts/run_exp_baseline.py --seed 42 --contract_variant answer_plus_evidence_guardrail_v2 --enforcement_policy retry_once_if_support_lt_0.5_else_force_unknown --retriever_type bm25 --top_k 10 --intent_mode rule_v1      --output_id exp_default_intent_rule_v1_real_v1`
  - `python scripts/run_exp_baseline.py --seed 42 --contract_variant answer_plus_evidence_guardrail_v2 --enforcement_policy retry_once_if_support_lt_0.5_else_force_unknown --retriever_type bm25 --top_k 10 --intent_mode rule_v1_route   --output_id exp_default_intent_route_real_v1`
  - `python scripts/run_exp_baseline.py --seed 42 --contract_variant answer_plus_evidence_guardrail_v2 --enforcement_policy retry_once_if_support_lt_0.5_else_force_unknown --retriever_type bm25 --top_k 10 --intent_mode rule_v1_clarify --output_id exp_default_intent_clarify_real_v1`

P0 阶段推荐流程：

1. 使用上述 4 条命令在 `runs/` 下得到对应主线 run；
2. 使用专门的收集脚本（例如 `intent_workspace/scripts/collect_mainline_intent_runs.py`，见后续实现）将主线 run 折叠为 `intent_workspace/runs/<timestamp>_<intent_mode>/` 结构，并补齐 `repro_manifest.json` / `config_snapshot.yaml` / `metrics.json` / `per_sample_intent_results.jsonl` / `run.log` / `summary.md`；
3. 最后通过 `scripts/intent_ablation_compare.py` 生成统一对比 JSON 与 CSV 表格（输出目录建议为 `intent_workspace/artifacts/`）。

## 索引文件（runs/_index/index.jsonl）

- 每次成功 run（所有必需文件存在且校验通过）后，都会在 `_index/index.jsonl` 追加一行 JSON：
  - `run_id`：本次运行 ID；
  - `datetime`：结束时间（ISO8601）；
  - `mode`：运行模式（当前实现主要为 `rule_predict`）；
  - `config_fingerprint`：本次配置指纹；
  - `input_hash`：主输入数据文件的 SHA256；
  - `key_metrics`：如 `macro_f1` / `ambiguous_rate` / `multi_intent_rate` 等；
  - `notes`：简短备注，可由 CLI 或后处理脚本写入。

## 审计字段要求（概览）

详尽字段说明见 `artifacts_schema.md`，核心要求：

- **可定位**：任何一次 run 都能追溯到具体代码版本、配置版本与输入数据版本；
- **可比较**：关键指标与配置指纹可在索引层面快速对比；
- **可重放**：给定 `run_id`，无需再查找其它路径即可重新运行或审计该实验。

