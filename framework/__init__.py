from __future__ import annotations

from pathlib import Path
import sys

# Project root = repo root (same as other scripts using ROOT)
ROOT: Path = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

__all__ = ["ROOT"]

