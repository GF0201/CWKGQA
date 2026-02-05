## P4-0 文件清单与可读性预检查（P4_file_inventory）

- **生成时间**：2026-02-05（本地时间）
- **根目录约定**：以下路径均以 `intent_workspace/` 为根。
- **结论概览**：
  - 题面要求的关键文件（paper_pack 文稿 / LaTeX 表 / appendix / artifacts / runs 索引）**全部存在且可读**。
  - JSON / JSONL / CSV 文件在抽样解析中均未发现格式错误。
  - **后续阶段 P4-1 ~ P4-7 均可按计划执行**，无因输入缺失而必须跳过的子任务。

---

### 1. paper_pack/text/*.md

已检查目录：`intent_workspace/paper_pack/text/`

```text
目录: D:\KGELLM\kgqa_framework\intent_workspace\paper_pack\text

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a----          2026/2/5     20:18           4426 intent_ablation_results_zh.md
-a----          2026/2/5     20:18           6082 intent_case_study_zh.md
-a----          2026/2/5     20:18           5454 intent_module_methods_zh.md
-a----          2026/2/5     20:18           3951 intent_thresholds_selection_zh.md
-a----          2026/2/5     20:18           8990 source_files_manifest.md
-a----          2026/2/5     20:18           6413 threats_to_validity_intent_zh.md
```

- **关键文件可读性**（抽样只读打开）：
  - `text/intent_ablation_results_zh.md`：Markdown 结构正常，可解析。
  - `text/threats_to_validity_intent_zh.md`：Markdown 结构正常，可解析。
  - `text/intent_thresholds_selection_zh.md`：Markdown 结构正常，可解析。
  - `text/source_files_manifest.md`：Markdown 结构正常，可解析。

---

### 2. paper_pack/latex/*.tex

已检查目录：`intent_workspace/paper_pack/latex/`

```text
目录: D:\KGELLM\kgqa_framework\intent_workspace\paper_pack\latex

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a----          2026/2/5     20:18           1527 intent_ablation_main_table.tex
-a----          2026/2/5     20:18           2078 intent_trigger_stats_table.tex
-a----          2026/2/5     20:18           1225 rules_trigger_frequency_table.tex
-a----          2026/2/5     20:18           2403 threshold_sweep_table.tex
```

- **关键文件可读性**（抽样只读打开）：
  - `latex/intent_ablation_main_table.tex`：LaTeX 表格结构完整，含 `tabular`、`tablenotes` 等环境。
  - `latex/intent_trigger_stats_table.tex`：LaTeX 表格结构完整，可作为后续 full/top-K 拆分模板。

---

### 3. paper_pack/appendix/*.md

已检查目录：`intent_workspace/paper_pack/appendix/`

```text
目录: D:\KGELLM\kgqa_framework\intent_workspace\paper_pack\appendix

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a----          2026/2/5     20:18           8477 intent_artifacts_schema.md
-a----          2026/2/5     20:18           7997 intent_audit_fields.md
-a----          2026/2/5     20:18           4466 intent_error_slices_summary.md
```

- **关键文件可读性**（抽样只读打开）：
  - `appendix/intent_error_slices_summary.md`：Markdown 结构正常，包含 EM/F1/unknown_rate 等近似数值摘要。

---

### 4. artifacts 关键工件

已检查目录：`intent_workspace/artifacts/`

```text
目录: D:\KGELLM\kgqa_framework\intent_workspace\artifacts

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a----          2026/2/5     18:45           4724 casebook.md
-a----          2026/2/5     18:45            413 error_slices.md
-a----          2026/2/5     18:40           4217 intent_ablation_compare.json
-a----          2026/2/5     18:40           1118 intent_ablation_main_table.csv
-a----          2026/2/5     18:42           3856 intent_gold_seed.jsonl
-a----          2026/2/5     18:40           1007 intent_trigger_stats.csv
-a----          2026/2/5     18:45            191 rules_trigger_frequency.csv
-a----          2026/2/5     18:43           3596 threshold_sweep_summary.csv
```

- **按任务要求的文件存在性与可读性**：
  - `artifacts/intent_ablation_main_table.csv`：CSV 头与数据行格式正确，可按列解析。
  - `artifacts/intent_trigger_stats.csv`：CSV 头与数据行格式正确，可按列解析。
  - `artifacts/threshold_sweep_summary.csv`：CSV 头与数据行格式正确，包含阈值组合与 `intent_config_fingerprint` 等字段。
  - `artifacts/rules_trigger_frequency.csv`：CSV 头与数据行格式正确。
  - `artifacts/intent_ablation_compare.json`：JSON 结构合法，含四个主线实验的 metrics 与 intent 字段。
  - `artifacts/casebook.md`：Markdown 结构正常，包含 Clarify-applied 等案例。
  - `artifacts/error_slices.md`：Markdown 结构正常，包含按 top1 intent 的误差切片表。

- **未发现的异常**：
  - 未发现缺失文件或无法打开的文件。
  - JSON 与 CSV 在抽样解析中均未出现格式错误。

---

### 5. runs/_index/index.jsonl

已检查目录：`intent_workspace/runs/_index/`

```text
目录: D:\KGELLM\kgqa_framework\intent_workspace\runs\_index

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a----          2026/2/5     18:39           1681 index.jsonl
```

- **文件可读性**：
  - `runs/_index/index.jsonl`：逐行 JSON 结构合法，包含四个主线 run：
    - `intent_20260205_183901_default_guardrail_v2_policyR_none`
    - `intent_20260205_183902_default_guardrail_v2_policyR_rule_v1`
    - `intent_20260205_183903_default_guardrail_v2_policyR_rule_v1_route`
    - `intent_20260205_183904_default_guardrail_v2_policyR_rule_v1_clarify`
  - 每行均包含 `run_id`、`datetime`、`mode`、`config_fingerprint`、`input_path`、`input_hash`、`key_metrics` 等字段，适合后续一致性校验脚本只读解析。

- **与后续阶段的关系**：
  - P4-2（阈值 sweep 最终状态澄清）将只读使用该文件中的 `config_fingerprint` 信息。
  - P4-6（只读一致性校验脚本）将基于此文件汇总主线 run 列表与 `intent_mode` / `key_metrics` 集合。

---

### 6. 预检查结论与后续阶段可执行性

- **缺失文件检查结果**：
  - 本次扫描中，题面列出的以下路径全部存在且可读：
    - `paper_pack/text/*.md`（包含指定的 `intent_ablation_results_zh.md`、`threats_to_validity_intent_zh.md`、`intent_thresholds_selection_zh.md`、`source_files_manifest.md`）
    - `paper_pack/latex/*.tex`（包含 `intent_ablation_main_table.tex`、`intent_trigger_stats_table.tex` 等）
    - `paper_pack/appendix/*.md`（包含 `intent_error_slices_summary.md` 等）
    - `artifacts/{intent_ablation_main_table.csv,intent_trigger_stats.csv,threshold_sweep_summary.csv,rules_trigger_frequency.csv,intent_ablation_compare.json,casebook.md,error_slices.md}`
    - `runs/_index/index.jsonl`
- **解析层面未发现阻断性问题**：
  - 抽样读取 JSON/JSONL/CSV 均成功，未发现导致后续逻辑无法继续的语法错误。

据此，本次 P4-0 预检查判定：**所有后续阶段（P4-1 ~ P4-7）均可在“不改配置/不重跑实验”的前提下按计划执行**，无须因输入缺失而提前终止。

