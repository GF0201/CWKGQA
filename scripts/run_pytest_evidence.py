#!/usr/bin/env python3
"""Run pytest and save output to runs/evidence_task4/artifacts/pytest.txt"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

art = ROOT / "runs" / "evidence_task4" / "artifacts"
art.mkdir(parents=True, exist_ok=True)

r = subprocess.run(
    [sys.executable, "-m", "pytest", "-q"],
    cwd=str(ROOT),
    capture_output=True,
    text=True,
)
out = (r.stdout or "") + (r.stderr or "")
(art / "pytest.txt").write_text(out, encoding="utf-8")
print(out)
sys.exit(r.returncode)
