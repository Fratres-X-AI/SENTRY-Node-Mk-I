#!/usr/bin/env python3
"""Aggregate RunPod MAX reports."""
from __future__ import annotations

import json
from pathlib import Path

root = Path(__file__).resolve().parents[2] / "validation" / "reports"
parts = {}
for name in [
    "defense-readiness-sentry.json",
    "runpod-mass-validation.json",
    "runpod-gpu-acoustic.json",
    "runpod-mesh-soak.json",
]:
    p = root / name
    if p.exists():
        parts[name] = json.loads(p.read_text())

summary = {
    "codename": "SENTRY",
    "mode": "runpod_max_summary",
    "reports": parts,
    "mass_runs": parts.get("runpod-mass-validation.json", {}).get("total_runs"),
}
(root / "runpod-max-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
