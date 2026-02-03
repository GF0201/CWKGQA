"""Dual logging: console + runs/<exp_id>/run.log."""
import sys
from pathlib import Path
from typing import Optional


class DualLogger:
    """Log to both console and a file."""

    def __init__(self, run_dir: Path, log_name: str = "run.log"):
        self.log_path = Path(run_dir) / log_name
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.log_path, "w", encoding="utf-8", buffering=1)

    def log(self, msg: str) -> None:
        line = msg if msg.endswith("\n") else msg + "\n"
        sys.stdout.write(line)
        sys.stdout.flush()
        self._file.write(line)
        self._file.flush()

    def close(self) -> None:
        self._file.close()
