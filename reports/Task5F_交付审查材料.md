# Task #5-F Fix2 验收回传（原文，不省略）

以下为真实运行后生成的文件本体或全文。

---

## a) reports/20260202_task4_domain_main_smoke__domain_main_smoke2.md 全文

```markdown
# Run Report: task4_domain_main_smoke / domain_main_smoke2

## 1. 基本信息

- **start_time**: 2026-02-02T22:32:42.760982
- **end_time**: 2026-02-02T22:32:42.763720
- **phase**: post_run
- **mode**: domain_main_smoke
- **seed**: 42
- **no_cache**: None
- **subprocess_return_code**: None
- **runner_name / task_name**: task4_domain_main_smoke

## 2. 命令

```
scripts/run_domain_main_smoke.py --data_file data/domain_main_demo.jsonl --limit 3 --seed 42 --output-id domain_main_smoke2
```

## 3. 输入指纹 (input_files_sha256)

总数: 4

### DATA::
- `DATA::domain_main_demo.jsonl`: `20697891333eda64bb23051498d3a20dd83c5326979df5e1070d43d246fa978d`

### OLD::
(无)

### NEW::
- `configs/default.yaml`: `223ff7211d94d391a1df2ad58bd5ba7856580fc97f310c5a8af37989f9261875`
- `requirements.txt`: `e88e5ee203fbc38463ff5c5d7292b726bce61f4751e4e39f8e8089477f9a76eb`
- `scripts/run_domain_main_smoke.py`: `ca3a4d6b4618d853ca6fdb8fdf6432a1e2fcb8609358b594e91d2aba0fd2e578`

## 4. 关键产物索引

- **repro_manifest.json**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke2\repro_manifest.json`
- **metrics.json**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke2\metrics.json`
- **artifacts/per_sample_results.jsonl**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke2\artifacts\per_sample_results.jsonl` (3 行)
- **artifacts/failures.csv**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke2\artifacts\failures.csv` (1 行)
- **artifacts/case_studies.md**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke2\artifacts\case_studies.md`
- **artifacts/kg_sample_audit.csv**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke2\artifacts\kg_sample_audit.csv`
- **artifacts/kg_sample_audit_summary.json**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke2\artifacts\kg_sample_audit_summary.json`
- **run.log**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke2\run.log`

## 5. 指标摘要 (metrics.json)

MISSING: metrics.json

## 6. 校验结果

- **validate_audit_artifacts**: N/A
- **来源**: domain_main_smoke runner does not call validate_audit_artifacts

## 7. Warnings

- (无)

## 8. failures.csv 按 error_type 计数 (top 10)

- (无失败行或文件不存在)

## 9. run.log 末尾 80 行

```
argv: scripts/run_domain_main_smoke.py --data_file data/domain_main_demo.jsonl --limit 3 --seed 42 --output-id domain_main_smoke2
domain_main smoke started
Run dir: C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke2
Data: data\domain_main_demo.jsonl
Limit: 3
Dataset validation: ok=3, bad=0, bad_path=None
Loaded 3 samples from data\domain_main_demo.jsonl
Saved repro_manifest.json
Inputs hashed: 4; first_keys=['DATA::domain_main_demo.jsonl', 'configs/default.yaml', 'requirements.txt']
domain_main smoke completed
Report saved to C:\Users\顾北上\KGELLM\kgqa_framework\reports\20260202_task4_domain_main_smoke__domain_main_smoke2.md
```
```

---

## b) runs/domain_main_smoke2/repro_manifest.json 关键字段片段

```json
{
  "run_id": "domain_main_smoke2",
  "phase": "post_run",
  "runner_name": "task4_domain_main_smoke",
  "command_argv": [
    "scripts/run_domain_main_smoke.py",
    "--data_file",
    "data/domain_main_demo.jsonl",
    "--limit",
    "3",
    "--seed",
    "42",
    "--output-id",
    "domain_main_smoke2"
  ],
  "seed": 42,
  "args": {
    "data_file": "data\\domain_main_demo.jsonl",
    "limit": 3,
    "seed": 42,
    "output_id": "domain_main_smoke2",
    "mode": "domain_main_smoke",
    "n_total": 3,
    "n_ok": 3,
    "n_bad": 0
  },
  "warnings": []
}
```

---

## c) runs/domain_main_smoke2/artifacts/failures.csv 前 10 行

```
qid,question,status,is_executable,http_status,error_type,em,f1,trace_path
```

---

## d) runs/domain_main_smoke2/run.log 末尾 80 行（含 "Report saved to …"）

```
argv: scripts/run_domain_main_smoke.py --data_file data/domain_main_demo.jsonl --limit 3 --seed 42 --output-id domain_main_smoke2
domain_main smoke started
Run dir: C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke2
Data: data\domain_main_demo.jsonl
Limit: 3
Dataset validation: ok=3, bad=0, bad_path=None
Loaded 3 samples from data\domain_main_demo.jsonl
Saved repro_manifest.json
Inputs hashed: 4; first_keys=['DATA::domain_main_demo.jsonl', 'configs/default.yaml', 'requirements.txt']
domain_main smoke completed
Report saved to C:\Users\顾北上\KGELLM\kgqa_framework\reports\20260202_task4_domain_main_smoke__domain_main_smoke2.md
```
