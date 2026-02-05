# TASK 18: Default Config Regression After Fix
# 需设置: $env:MKEAI_API_KEY = "sk-..."

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ROOT

# Run 18.4: Regression Smoke v2
python scripts/run_exp_baseline.py `
  --retriever_type bm25 --top_k 10 `
  --output_id exp_default_config_smoke_real_v2_after_fix `
  --ablation default_config_smoke `
  --contract_variant answer_plus_evidence_guardrail_v2

# baseline_diagnose
python scripts/baseline_diagnose.py --run_dir runs/exp_default_config_smoke_real_v2_after_fix

# Retry Benefit Audit (fixed logic)
python scripts/retry_benefit_audit.py --run_dir runs/exp_default_config_smoke_real_v2_after_fix --fixed

Write-Host "TASK 18 regression done."
