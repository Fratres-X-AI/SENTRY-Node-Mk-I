"""Run full SENTRY simulation suite, failure modes, and defense-readiness report."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "implementation" / "src"
sys.path.insert(0, str(SRC))

from sentry.failure_modes import run_all as run_failure_modes  # noqa: E402
from sentry.hardware.probe import probe_all  # noqa: E402
from sentry.ingest import run_live_ingest  # noqa: E402

REPORTS = ROOT / "validation" / "reports"
SCENARIOS = ["benign", "intrusion", "jamming", "low_visibility"]
ENV = {**os.environ, "PYTHONPATH": str(SRC)}


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    ok = True

    for scenario in SCENARIOS:
        proc = subprocess.run(
            [sys.executable, "-m", "sentry", "--scenario", scenario, "--output", str(REPORTS)],
            cwd=str(ROOT),
            env=ENV,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            ok = False
            results.append({"scenario": scenario, "status": "FAIL", "stderr": proc.stderr.strip()})
            continue

        summary = json.loads(proc.stdout.strip().splitlines()[-1])
        passed = summary.get("audit_chain_valid") and summary.get("frames", 0) > 0
        if scenario == "benign" and summary.get("max_level") not in {"CLEAR", "YELLOW"}:
            passed = False
        if scenario == "intrusion" and summary.get("max_level") not in {"ORANGE", "RED", "YELLOW"}:
            passed = False
        if scenario == "jamming" and summary.get("max_level") != "HOLD":
            passed = False

        if not passed:
            ok = False
        results.append({"scenario": scenario, "status": "PASS" if passed else "FAIL", **summary})

    node_config = json.loads((ROOT / "configs" / "sentry_node_config.json").read_text(encoding="utf-8"))
    mission = json.loads((ROOT / "configs" / "sentry_mission_profile.json").read_text(encoding="utf-8"))
    probe_report = probe_all(node_config)

    failure_report = run_failure_modes()
    if failure_report.get("overall") != "PASS":
        ok = False

    live_summary = run_live_ingest(
        node_id=node_config.get("node_id", "sentry-pi-zero-001"),
        mission=mission,
        node_config=node_config,
        duration_s=4.0,
        rate_hz=1.0,
        output_dir=REPORTS,
    )
    if not live_summary.get("frames"):
        ok = False

    deployment_report: dict = {}
    try:
        from sentry.deployment.config import ChainDeploymentConfig
        from sentry.deployment.manager import DeploymentManager
        from sentry.deployment.monte_carlo_impact import gpu_monte_carlo_deployment

        chain_cfg = json.loads((ROOT / "configs" / "deployment_chain_alpha.json").read_text(encoding="utf-8"))
        dep = chain_cfg.get("deployment", {})
        mgr = DeploymentManager(ChainDeploymentConfig.from_dict(dep), chain_cfg.get("chain_id", "CHAIN-AUDIT"))
        deployment_report["sequence"] = mgr.full_deploy_sequence()
        deployment_report["monte_carlo"] = gpu_monte_carlo_deployment(
            total=5000,
            config=ChainDeploymentConfig.from_dict(dep),
        ).to_dict()
        deployment_report["line_charge_reference"] = __import__(
            "sentry.deployment.physics", fromlist=["simulate_line_deployment"]
        ).simulate_line_deployment(
            ChainDeploymentConfig.from_dict({**dep, "launch_method": "line_charge_reference"})
        ).to_dict()
        if deployment_report["line_charge_reference"].get("operational_nodes", 0) != 0:
            ok = False
    except Exception as exc:  # noqa: BLE001
        deployment_report = {"error": str(exc)}
        ok = False

    report = {
        "codename": "SENTRY",
        "type_designation": "AN/GSQ-100(V)1",
        "common_name": "SENTRY Node Mk I",
        "role_descriptor": "Passive Multi-Sensor Early-Warning Node (PMSEWN)",
        "project": "SENTRY-Node-Mk-I",
        "version": "0.3.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "defensive-only",
        "hardware_profile": "raspberry-pi-zero-2-w",
        "overall": "PASS" if ok else "FAIL",
        "scenarios": results,
        "hardware_probe": probe_report,
        "failure_modes": failure_report,
        "live_ingest_smoke": live_summary,
        "deployment_chain": deployment_report,
    }
    out_path = REPORTS / "defense-readiness-sentry.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
