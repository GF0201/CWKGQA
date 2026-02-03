# Run Report: task4_domain_main_smoke / domain_main_smoke_verify

## 1. 基本信息

- **start_time**: 2026-02-02T20:40:58.043934
- **end_time**: 2026-02-02T20:40:58.046031
- **phase**: domain_main_smoke
- **mode**: domain_main_smoke
- **seed**: 42
- **no_cache**: None
- **subprocess_return_code**: None

## 2. 命令

```
scripts/run_domain_main_smoke.py --data_file data/domain_main_demo.jsonl --limit 3 --seed 42 --output-id domain_main_smoke_verify
```

## 3. 输入指纹 (input_files_sha256)

总数: 4

### DATA::
- `DATA::domain_main_demo.jsonl`: `20697891333eda64bb23051498d3a20dd83c5326979df5e1070d43d246fa978d`

### OLD::

### NEW
- `configs/default.yaml`: `223ff7211d94d391a1df2ad58bd5ba7856580fc97f310c5a8af37989f9261875`
- `requirements.txt`: `e88e5ee203fbc38463ff5c5d7292b726bce61f4751e4e39f8e8089477f9a76eb`
- `scripts/run_domain_main_smoke.py`: `dc1a89a09fe45a3beef11d434f7056e5389b614770a35e8c48cc900a0ef44e16`

## 4. 关键产物索引

- **repro_manifest.json**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke_verify\repro_manifest.json`
- **metrics.json**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke_verify\metrics.json`
- **artifacts/per_sample_results.jsonl**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke_verify\artifacts\per_sample_results.jsonl` (3 行)
- **artifacts/failures.csv**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke_verify\artifacts\failures.csv` (1 行)
- **artifacts/case_studies.md**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke_verify\artifacts\case_studies.md`
- **artifacts/kg_sample_audit.csv**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke_verify\artifacts\kg_sample_audit.csv`
- **artifacts/kg_sample_audit_summary.json**: MISSING: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke_verify\artifacts\kg_sample_audit_summary.json`
- **run.log**: `C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke_verify\run.log`

## 5. 指标摘要 (metrics.json)

MISSING: metrics.json

## 6. 校验结果

- validate_audit_artifacts / validate_metrics: **N/A (no validate log)**

## 7. Warnings 与失败归因摘要

- (无)

**failures.csv 按 error_type 计数 (top 10)**

- (无失败行或文件不存在)

## 8. run.log 末尾 80 行

```
argv: scripts/run_domain_main_smoke.py --data_file data/domain_main_demo.jsonl --limit 3 --seed 42 --output-id domain_main_smoke_verify
domain_main smoke started
Run dir: C:\Users\顾北上\KGELLM\kgqa_framework\runs\domain_main_smoke_verify
Data: data\domain_main_demo.jsonl
Limit: 3
Dataset validation: ok=3, bad=0, bad_path=None
Loaded 3 samples from data\domain_main_demo.jsonl
Saved repro_manifest.json
Inputs hashed: 4; first_keys=['DATA::domain_main_demo.jsonl', 'configs/default.yaml', 'requirements.txt']
domain_main smoke completed
```