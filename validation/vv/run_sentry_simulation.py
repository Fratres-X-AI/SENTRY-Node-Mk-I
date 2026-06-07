"""Smoke test: single intrusion simulation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "validation" / "reports"


def main() -> int:
    import os

    env = {**os.environ, "PYTHONPATH": str(ROOT / "implementation" / "src")}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "sentry",
            "--scenario",
            "intrusion",
            "--duration",
            "15",
            "--output",
            str(REPORTS),
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return proc.returncode
    summary = json.loads(proc.stdout.strip().splitlines()[-1])
    out = REPORTS / "sentry-observe-smoke.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
