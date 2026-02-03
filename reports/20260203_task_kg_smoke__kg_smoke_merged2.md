# Run Report: task_kg_smoke / kg_smoke_merged2

## 1. 基本信息

- **start_time**: 2026-02-03T14:31:26.539159
- **end_time**: 2026-02-03T14:31:26.565165
- **phase**: post_run
- **mode**: 
- **seed**: 42
- **no_cache**: None
- **subprocess_return_code**: None
- **runner_name / task_name**: task_kg_smoke

## 2. 命令

```
scripts/run_kg_smoke.py --triples datasets/domain_main_kg/processed/merged/triples.jsonl --index_dir datasets/domain_main_kg/index --output-id kg_smoke_merged2 --seed 42 --audit-n 50
```

## 3. 输入指纹 (input_files_sha256)

总数: 4

### DATA::
- `DATA::triples.jsonl`: `759c838b3f68072652e069b0591effd7b99a7d448c9d3b38d745cd75fb6d173b`

### OLD::
(无)

### NEW::
- `datasets/domain_main_kg/index/forward.json`: `8fcb3cae7f13d34fdaabb3c8c50f52d2cc33e2fdca4b896cdefaa4d3874a8920`
- `datasets/domain_main_kg/index/backward.json`: `df9314caf9d306ea4d90ae5261e54aebb01d85023f0e7c2d410b31066f8b44df`
- `datasets/domain_main_kg/index/hp_to_t.json`: `9e27486113be1086b0828e2b212bafffc34fddd7a249c96634da5aa16263e562`

## 4. 关键产物索引

- **repro_manifest.json**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged2\repro_manifest.json`
- **metrics.json**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged2\metrics.json`
- **artifacts/per_sample_results.jsonl**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged2\artifacts\per_sample_results.jsonl` (9 行)
- **artifacts/failures.csv**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged2\artifacts\failures.csv` (header=1, failure_rows=0)
- **artifacts/case_studies.md**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged2\artifacts\case_studies.md`
- **artifacts/kg_sample_audit.csv**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged2\artifacts\kg_sample_audit.csv`
- **artifacts/kg_sample_audit_summary.json**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged2\artifacts\kg_sample_audit_summary.json`
- **run.log**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\kg_smoke_merged2\run.log`

## 5. 指标摘要 (metrics.json)

| 层级 | n | EM | F1 |
|------|---|----|----|
| total |  | null | null |
| executable_or_answerable |  | null | null |

**说明**: 未计算，原因见 warnings

## 6. 校验结果

- **validate_audit_artifacts**: PASS
- **来源**: run.log contains 'validate_audit_artifacts: PASS'

## 7. Warnings

- (无)

## 8. failures.csv 按 error_type 计数 (top 10)

- 无失败行（表头+0行数据）

## 9. run.log 末尾 80 行

```
argv: scripts/run_kg_smoke.py --triples datasets/domain_main_kg/processed/merged/triples.jsonl --index_dir datasets/domain_main_kg/index --output-id kg_smoke_merged2 --seed 42 --audit-n 50
KG smoke started
Loaded 3078 triples
Metrics: n_triples=3078, n_entities=4070, n_relations=769, density=0.000186
Wrote kg_sample_audit.csv with 50 rows
Wrote case_studies.md with 8 samples
KG smoke completed
validate_audit_artifacts: PASS
```