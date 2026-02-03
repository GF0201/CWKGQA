# KGQA Reproducible Experiment Framework

通用可复现实验框架，支持 smoke 测试与 LC-QuAD2 + WDQS 实验迁移。

## 结构

```
kgqa_framework/
├── core/           # 复现能力
│   ├── seed.py     # 统一 random/numpy/torch seed
│   ├── logging.py  # 控制台 + run.log
│   ├── repro.py    # repro_manifest.json
│   ├── io.py       # JSON/JSONL
│   └── metrics.py  # two-level metrics
├── datasets/
│   ├── lcquad2_wdqs/   # LC-QuAD2 + WDQS 适配器
│   └── domain_stub/    # smoke 空壳
├── scripts/
│   ├── run_smoke.py
│   ├── run_lcquad2_dev200.py
│   └── gen_audit_old.py
├── configs/
├── runs/
└── _audit_old/     # 旧实验审计清单
```

## 运行

### Smoke
```bash
python scripts/run_smoke.py
```

### LC-QuAD2 dev200
```bash
# 使用旧实验管线（需 OLD_DIR 存在）
python scripts/run_lcquad2_dev200.py --data_file C:\Users\顾北上\KGELLM\kgqa-thesis\data\processed\unified\unified_dev.jsonl --limit 10

# 仅 mock（无旧管线）
python scripts/run_lcquad2_dev200.py --data_file data.jsonl --limit 5 --mock
```

### 生成旧实验审计
```bash
python scripts/gen_audit_old.py
```
