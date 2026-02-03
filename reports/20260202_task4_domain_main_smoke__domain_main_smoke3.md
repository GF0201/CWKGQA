# Run Report: task4_domain_main_smoke / domain_main_smoke3

## 1. 基本信息

- **start_time**: 2026-02-02T23:32:45.093828
- **end_time**: 2026-02-02T23:32:45.096034
- **phase**: post_run
- **mode**: domain_main_smoke
- **seed**: 42
- **no_cache**: None
- **subprocess_return_code**: None
- **runner_name / task_name**: task4_domain_main_smoke

## 2. 命令

```
scripts\run_domain_main_smoke.py --data_file data\domain_main_demo.jsonl --limit 3 --seed 42 --output-id domain_main_smoke3
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
- `scripts/run_domain_main_smoke.py`: `9cfd25ca80b3170aa1f42ddfe950834c006bab94453b8b8a5a387210e9e89f0a`

## 4. 关键产物索引

- **repro_manifest.json**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke3\repro_manifest.json`
- **metrics.json**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke3\metrics.json`
- **artifacts/per_sample_results.jsonl**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke3\artifacts\per_sample_results.jsonl` (3 行)
- **artifacts/failures.csv**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke3\artifacts\failures.csv` (header=1, failure_rows=0)
- **artifacts/case_studies.md**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke3\artifacts\case_studies.md`
- **artifacts/kg_sample_audit.csv**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke3\artifacts\kg_sample_audit.csv`
- **artifacts/kg_sample_audit_summary.json**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke3\artifacts\kg_sample_audit_summary.json`
- **run.log**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke3\run.log`

## 5. 指标摘要 (metrics.json)

MISSING: metrics.json

## 6. 校验结果

- **validate_audit_artifacts**: PASS
- **来源**: run.log contains 'validate_audit_artifacts: PASS'

## 7. Warnings

- (无)

## 8. failures.csv 按 error_type 计数 (top 10)

- 无失败行（表头+0行数据）

## 9. run.log 末尾 80 行

```
argv: scripts\run_domain_main_smoke.py --data_file data\domain_main_demo.jsonl --limit 3 --seed 42 --output-id domain_main_smoke3
domain_main smoke started
Run dir: C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke3
Data: data\domain_main_demo.jsonl
Limit: 3
Dataset validation: ok=3, bad=0, bad_path=None
Loaded 3 samples from data\domain_main_demo.jsonl
Saved repro_manifest.json
Inputs hashed: 4; first_keys=['DATA::domain_main_demo.jsonl', 'configs/default.yaml', 'requirements.txt']
domain_main smoke completed
validate_audit_artifacts: PASS
```