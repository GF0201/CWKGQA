# Run Report: task_kg_smoke / kg_smoke_merged1

## 1. 基本信息

- **start_time**: 2026-02-03T00:19:57.017873
- **end_time**: 2026-02-03T00:19:57.068493
- **phase**: post_run
- **mode**: 
- **seed**: 42
- **no_cache**: None
- **subprocess_return_code**: None
- **runner_name / task_name**: task_kg_smoke

## 2. 命令

```
scripts/run_kg_smoke.py --triples datasets/domain_main_kg/processed/merged/triples.jsonl --index_dir datasets/domain_main_kg/index --output-id kg_smoke_merged1 --seed 42
```

## 3. 输入指纹 (input_files_sha256)

总数: 1

### DATA::
- `DATA::triples.jsonl`: `759c838b3f68072652e069b0591effd7b99a7d448c9d3b38d745cd75fb6d173b`

### OLD::
(无)

### NEW::
(无)

## 4. 关键产物索引

- **repro_manifest.json**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged1\repro_manifest.json`
- **metrics.json**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged1\metrics.json`
- **artifacts/per_sample_results.jsonl**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged1\artifacts\per_sample_results.jsonl` (9 行)
- **artifacts/failures.csv**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged1\artifacts\failures.csv` (header=1, failure_rows=0)
- **artifacts/case_studies.md**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged1\artifacts\case_studies.md`
- **artifacts/kg_sample_audit.csv**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged1\artifacts\kg_sample_audit.csv`
- **artifacts/kg_sample_audit_summary.json**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged1\artifacts\kg_sample_audit_summary.json`
- **run.log**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged1\run.log`

## 5. 指标摘要 (metrics.json)

MISSING: metrics.json

## 6. 校验结果

- **validate_audit_artifacts**: PASS
- **来源**: run.log contains 'validate_audit_artifacts: PASS'

## 7. Warnings

- Failed to hash datasets\domain_main_kg\index: PermissionError(13, 'Permission denied')

## 8. failures.csv 按 error_type 计数 (top 10)

- 无失败行（表头+0行数据）

## 9. run.log 末尾 80 行

```
argv: scripts/run_kg_smoke.py --triples datasets/domain_main_kg/processed/merged/triples.jsonl --index_dir datasets/domain_main_kg/index --output-id kg_smoke_merged1 --seed 42
KG smoke started
Loaded 3078 triples
KG smoke completed
validate_audit_artifacts: PASS
```