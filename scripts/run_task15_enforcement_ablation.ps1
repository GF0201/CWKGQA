# TASK 15: Enforcement Policy Ablation
# 在 support_semantics_version="raw_answer_only_v1" 下对比 Policy B vs Policy R
# 需要设置环境变量: $env:MKEAI_API_KEY = "sk-your-key"

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ROOT

# Run B2: Policy B
python scripts/run_exp_baseline.py `
  --retriever_type bm25 --top_k 10 `
  --output_id exp_guardrail_v2_policyB_fixedsupport_bm25_k10_real_v1 `
  --ablation enforcement_policy `
  --contract_variant answer_plus_evidence_guardrail_v2 `
  --enforcement_policy force_unknown_if_support_lt_0.5

# Run R: Policy R
python scripts/run_exp_baseline.py `
  --retriever_type bm25 --top_k 10 `
  --output_id exp_guardrail_v2_policyR_retry_once_then_force_unknown_fixedsupport_bm25_k10_real_v1 `
  --ablation enforcement_policy `
  --contract_variant answer_plus_evidence_guardrail_v2 `
  --enforcement_policy retry_once_if_support_lt_0.5_else_force_unknown

# baseline_diagnose for B2
python scripts/baseline_diagnose.py --run_dir runs/exp_guardrail_v2_policyB_fixedsupport_bm25_k10_real_v1

# baseline_diagnose for R
python scripts/baseline_diagnose.py --run_dir runs/exp_guardrail_v2_policyR_retry_once_then_force_unknown_fixedsupport_bm25_k10_real_v1

# Generate enforcement_policy_compare.json
python scripts/enforcement_policy_compare.py `
  --run_policy_b runs/exp_guardrail_v2_policyB_fixedsupport_bm25_k10_real_v1 `
  --run_policy_r runs/exp_guardrail_v2_policyR_retry_once_then_force_unknown_fixedsupport_bm25_k10_real_v1 `
  --output_dir runs/exp_guardrail_v2_policyR_retry_once_then_force_unknown_fixedsupport_bm25_k10_real_v1

Write-Host "TASK 15 done. Check runs/.../artifacts/enforcement_policy_compare.json"
