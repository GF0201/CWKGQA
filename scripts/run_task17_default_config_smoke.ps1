# TASK 17: Default Config Regression + Retry Benefit Audit
# 需设置: $env:MKEAI_API_KEY = "sk-..."

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ROOT

# Run 17.1: Default Config Smoke (Real)
python scripts/run_exp_baseline.py `
  --retriever_type bm25 --top_k 10 `
  --output_id exp_default_config_smoke_real_v1 `
  --ablation default_config_smoke `
  --contract_variant answer_plus_evidence_guardrail_v2

# baseline_diagnose for required artifacts
python scripts/baseline_diagnose.py --run_dir runs/exp_default_config_smoke_real_v1

# Run 17.2: Retry Benefit Audit
python scripts/retry_benefit_audit.py --run_dir runs/exp_default_config_smoke_real_v1

Write-Host "TASK 17 done."
