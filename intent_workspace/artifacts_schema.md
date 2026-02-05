## intent_workspace 运行产物规范（artifacts schema）

本文件约定 `intent_workspace/runs/<run_id>/` 目录下 **每次运行必须产出** 的文件及核心字段，方便审计与自动校验。

---

## 顶层目录结构

每个 `run_id` 目录下至少包含：

- `repro_manifest.json`
- `config_snapshot.yaml`
- `metrics.json`
- `per_sample_intent_results.jsonl`
- `run.log`
- `summary.md`

如缺失任意一个文件，主脚本会在结束前给出提示并以 **非零退出码** 结束。

---

## A. repro_manifest.json

**类型**：JSON 对象  
**用途**：可复现性与环境审计。

关键字段（部分来自 `core.write_repro_manifest`，部分由意图模块追加）：

- `run_id`: `string` — 本次运行 ID。
- `start_time`: `string` — 运行开始时间（ISO8601）。
- `end_time`: `string` — 运行结束时间（ISO8601）。
- `python_version`: `string` — 完整 Python 版本字符串。
- `env_summary`: `object` — 轻量环境摘要（含 OS / platform）。
- `platform`: `object` — 详细平台信息（OS、hostname 等）。
- `pip_freeze`: `string` — `pip freeze` 文本。
- `requirements_sha256`: `string` — `requirements.txt` 或 `pip_freeze` 的哈希。
- `command_line`: `string` — 原始命令行。
- `command_argv`: `string[]` — argv 列表。
- `seed`: `integer` — 随机种子。
- `input_files_sha256`: `object<string,string>`  
  - key：归一化后的路径标识（例如 `DATA::test.jsonl`）  
  - value：文件的 SHA256。
- `data_hashes`: `object<string,string>`  
  - 语义上等价于“输入数据与配置类文件的哈希”，是 `input_files_sha256` 的子集或重排，便于审计直接使用。
- `config`: `object` — 运行时使用的配置字典（可与 `config_snapshot.yaml` 对应）。
- `args`: `object` — 解析后的 CLI 参数。
- `warnings`: `string[]` — 运行过程中产生的警告信息。
- `output_dir`: `string` — 运行输出目录的绝对路径。

意图识别模块新增/约定字段：

- `git_commit`: `string | null`  
  - 当前 `HEAD` 的 git commit hash，若获取失败则为 `null`。
- `config_fingerprint`: `string`  
  - 对“实际生效配置”的 canonical JSON 做 SHA256 得到的指纹。
- `audit_overrides`: `object[]`（可选，默认为空）  
  - CLI 覆盖信息，典型元素示例：
  - `{ "arg": "--threshold_multi", "old": 0.5, "new": 0.7 }`
- `fingerprint_overridden`: `string`（可选）  
  - 如存在 overrides，可记录覆盖后实际指纹；当前实现中该字段接口保留，若无 overrides 则与 `config_fingerprint` 相同。

---

## B. config_snapshot.yaml

**类型**：YAML  
**用途**：记录“展开后”的完整配置快照。

推荐结构：

```yaml
effective_config:
  defaults:  # intent_experiment_defaults.yaml 完整内容
    ...
  taxonomy:  # intent_taxonomy.yaml 完整内容
    ...
  rules:     # intent_rules.yaml 完整内容
    ...
  thresholds:
    multi_intent: float
    ambiguous: float
  cli_overrides:    # 解析后的 CLI 覆盖（若无则为空列表或空字典）
    - arg: string
      old: any
      new: any

audit:
  config_fingerprint: string
  fingerprint_overridden: string
  git_commit: string | null
```

审计原则：

- `effective_config` 中不应残留“隐式默认值”，所有实际使用到的阈值与标志位都要显式写出；
- `audit.config_fingerprint` 必须与 `repro_manifest.json.config_fingerprint` 一致。

---

## C. metrics.json

**类型**：JSON 对象  
**用途**：聚合级别的意图识别效果与规则覆盖统计。

顶层结构建议：

```json
{
  "overall": {
    "macro_f1": 0.0,
    "micro_f1": 0.0,
    "multi_intent_accuracy": 0.0,
    "ambiguous_rate": 0.0,
    "multi_intent_rate": 0.0,
    "coverage_rate": 0.0
  },
  "per_label": {
    "LABEL_A": {
      "precision": 0.0,
      "recall": 0.0,
      "f1": 0.0,
      "support": 0
    }
  },
  "rule_stats": {
    "n_samples": 0,
    "n_with_any_rule": 0
  },
  "audit": {
    "config_fingerprint": "",
    "input_path": "",
    "input_hash": "",
    "git_commit": null
  }
}
```

说明：

- 若无 gold intent labels：
  - `macro_f1` / `micro_f1` / `multi_intent_accuracy` 等可置为 `null`；
  - 但 `ambiguous_rate` / `multi_intent_rate` / `coverage_rate` 仍应根据规则触发情况计算；
  - `per_label` 中的 `precision` / `recall` / `f1` 可为 `null`，`support` 为 0。
- 若存在 gold/silver labels：
  - 需按常规定义计算 macro/micro F1 与 per-label 指标（后续实现可在此基础上扩展）。

---

## D. per_sample_intent_results.jsonl

**类型**：JSONL（每行一个样本）  
**用途**：样本级诊断与审计。

每行必须至少包含以下字段：

- `id`: `string` — 唯一样本 ID（如 `draft_0`）。
- `question`: `string` — 原始问题文本。
- `gold_intents`: `string[] | null` — gold 意图标签；无标签时为 `null`。
- `pred_intents`: `object[]` — 预测意图列表，示例：
  - `{ "label": "MULTI_FACT", "score": 1.5 }`
- `is_multi_intent`: `boolean` — 是否判定为多意图问题。
- `is_ambiguous`: `boolean` — 是否判定为存在歧义。
- `clarification_question`: `string | null` — 若 `is_ambiguous == true`，可给出澄清问题建议，否则为 `null`。
- `clarification_options`: `string[] | null` — 可选澄清选项列表，无则为 `null`。
- `rules_fired`: `object[]` — 触发的规则清单，示例：
  - `{ "rule_id": "multi_and", "label": "MULTI_FACT", "weight": 1.0 }`
- `thresholds_used`: `object` — 本样本实际使用到的阈值配置（通常与全局阈值一致）。

---

## E. run.log

**类型**：纯文本（UTF-8）  
**用途**：人类可读的运行过程日志，配合其它产物进行排障。

最低要求：

- 首尾各至少一条时间戳日志；
- 必须包含：
  - 输入数据路径与条数；
  - 随机种子与关键阈值；
  - `run_id` 与 `config_fingerprint`；
  - 运行模式（rule_predict / report / …）；
  - 总耗时（秒级）。

推荐使用已有的 `core.DualLogger` 实现。

---

## F. summary.md

**类型**：Markdown  
**用途**：简短的人类可读总结，便于在审查报告或对比分析中引用。

内容建议（3–10 行）：

- 本次运行的目的与配置 tag（如“多意图规则 v1 / 默认阈值”等）；
- 关键指标摘要：macro/micro F1、多意图/歧义检出率、规则覆盖率等；
- 与历史 run 的对比（若有明显变化，可简单点出）；
- 主要发现、问题与后续改进方向。

---

## 索引文件：runs/_index/index.jsonl

**类型**：JSONL  
**用途**：跨 run 聚合与快速对比。

每行对应一个成功运行（所有必需文件存在且校验通过），字段包括：

- `run_id`: `string`
- `datetime`: `string` — 运行结束时间。
- `mode`: `string` — 运行模式。
- `config_fingerprint`: `string`
- `input_hash`: `string`
- `key_metrics`: `object` — 至少包含：
  - `macro_f1`
  - `ambiguous_rate`
  - `multi_intent_rate`
- `notes`: `string` — 可选备注（例如“rule-only baseline”）。

该文件由 `run_intent_exp.py` 在每次成功 run 后自动追加，无需手工编辑。

