"""Defense readiness simulation suite for SENTRY."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    audit = ROOT / "run_complete_audit.py"
    proc = subprocess.run([sys.executable, str(audit)], cwd=str(ROOT))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
