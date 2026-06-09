"""Verify repo is ready for physical build (software gate)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "implementation" / "src"
sys.path.insert(0, str(SRC))

REQUIRED_PATHS = [
    "docs/BUILD_STAGE.md",
    "docs/build_assembly.md",
    "docs/sd_flash_checklist.md",
    "docs/system_datasheet.md",
    "configs/procurement_bom.json",
    "configs/deployment_site_alpha.json",
    "configs/sentry_mission_profile.json",
    "deploy/bootstrap_pi_zero.sh",
    "deploy/sentry-guardian.service",
    "implementation/pyproject.toml",
    "run_complete_audit.py",
]

REQUIRED_NODE_CONFIGS = [
    "configs/nodes/sentry-pi-zero-001.json",
    "configs/nodes/sentry-pi-zero-002.json",
    "configs/nodes/sentry-pi-zero-003.json",
    "configs/nodes/sentry-pi-zero-004.json",
]


def main() -> int:
    missing: list[str] = []
    for rel in REQUIRED_PATHS + REQUIRED_NODE_CONFIGS:
        if not (ROOT / rel).exists():
            missing.append(rel)

    if missing:
        print("BUILD READINESS: FAIL — missing files:")
        for m in missing:
            print(f"  - {m}")
        return 1

    # Schema sanity on procurement + site manifest
    proc = json.loads((ROOT / "configs/procurement_bom.json").read_text(encoding="utf-8"))
    site = json.loads((ROOT / "configs/deployment_site_alpha.json").read_text(encoding="utf-8"))
    if proc.get("per_node_subtotal_usd", 0) < 100:
        print("BUILD READINESS: FAIL — procurement BOM looks incomplete")
        return 1
    if len(site.get("nodes", [])) != 4:
        print("BUILD READINESS: FAIL — site manifest needs 4 nodes")
        return 1

    # Node configs: simulation must be off for build templates
    for rel in REQUIRED_NODE_CONFIGS:
        cfg = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        if cfg.get("simulation", {}).get("enabled", True):
            print(f"BUILD READINESS: WARN — {rel} has simulation.enabled=true (use false for field build)")

    # Quick import check
    from sentry.guardian import SentryGuardian  # noqa: F401
    from sentry.deployment.manager import DeploymentManager  # noqa: F401

    # Pytest (exclude gpu)
    proc_test = subprocess.run(
        [sys.executable, "-m", "pytest", "implementation/tests/", "-q", "-k", "not gpu"],
        cwd=str(ROOT),
        env={**dict(__import__("os").environ), "PYTHONPATH": str(SRC)},
        capture_output=True,
        text=True,
    )
    if proc_test.returncode != 0:
        print("BUILD READINESS: FAIL — pytest")
        print(proc_test.stdout[-2000:])
        print(proc_test.stderr[-2000:])
        return 1

    report = {
        "codename": "SENTRY",
        "type_designation": "AN/GSQ-100(V)1",
        "gate": "build_readiness_software",
        "version": "0.4.0-build",
        "overall": "PASS",
        "checks": {
            "required_files": len(REQUIRED_PATHS) + len(REQUIRED_NODE_CONFIGS),
            "site_nodes": 4,
            "pytest": "PASS",
        },
        "next_physical_gates": ["G1 probe", "G2 RF", "G3 acoustic", "G4 mesh", "G5 soak"],
        "runpod_required": False,
    }
    out = ROOT / "validation" / "reports" / "build-readiness.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
