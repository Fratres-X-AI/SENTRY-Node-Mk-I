"""CLI entrypoints for SENTRY guard and simulation."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from sentry.audit import AuditLogger, AuditStore, AuditStoreConfig
from sentry.failure_modes import run_all as run_failure_modes
from sentry.guardian import SentryGuardian
from sentry.hardware.probe import probe_all
from sentry.ingest import run_live_ingest
from sentry.sensors.power_metrics import PowerMetrics, PowerMetricsConfig
from sentry.schema_validate import validate
from sentry.simulation.synthetic import SimulatedSensorArray, scenario_from_name

LOG = logging.getLogger("SENTRY")


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _setup_logging(prefix: str = "SENTRY") -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{prefix}] %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


_GATE_REMEDIATION = {
    "pir_gpio": [
        "PIR OUT -> GPIO17 (pin 11), VCC -> 5V (pin 2), GND -> GND (pin 6).",
        "Off-Pi this reports unavailable by design; run on the Pi.",
        "sudo usermod -aG gpio $USER && sudo reboot",
    ],
    "acoustic_sensor": [
        "sudo apt-get install -y portaudio19-dev && pip install -e 'implementation[hardware]'",
        "Verify mic: arecord -l   (expect a USB card).",
        "Replug mic into a powered hub port.",
    ],
    "rf_sensor": [
        "sudo apt-get install -y rtl-sdr librtlsdr-dev",
        "echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/rtl-sdr-blacklist.conf && sudo reboot",
        "rtl_test -t   (expect 'Found 1 device'). Use TCXO RTL-SDR Blog V3; clones fail.",
    ],
    "visual": ["Optional. If unused, ignore. Else check /dev/video0 and enable camera."],
    "tamper_gpio": [
        "Reed switch -> GPIO27 (pin 13) and GND; pull-up active-low. Run on the Pi.",
    ],
    "meshtastic_handler": [
        "ls -l /dev/ttyACM* /dev/meshtastic   (expect the T-Beam serial device).",
        "sudo cp deploy/99-sentry.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger",
        "Confirm SX1262 variant + Meshtastic firmware. sudo usermod -aG dialout $USER && sudo reboot",
    ],
}


def _run_g1_report(node_config: dict[str, Any]) -> dict[str, Any]:
    """G1 BIT: structured PASS/FAIL with remediation for every failed adapter."""
    from sentry.hardware import is_raspberry_pi

    report = probe_all(node_config)
    required = {"pir_gpio", "acoustic_sensor", "rf_sensor", "tamper_gpio", "meshtastic_handler"}
    failures = []
    for adapter in report["adapters"]:
        if adapter["adapter"] in required and not adapter["available"]:
            failures.append(
                {
                    "adapter": adapter["adapter"],
                    "detail": adapter["detail"],
                    "remediation": _GATE_REMEDIATION.get(adapter["adapter"], ["Inspect adapter detail."]),
                }
            )
    passed = len(failures) == 0 and is_raspberry_pi()
    return {
        "codename": "SENTRY",
        "type_designation": "AN/GSQ-100(V)1",
        "gate": "G1",
        "name": "Hardware probe (BIT)",
        "pi_detected": is_raspberry_pi(),
        "available_count": report["available_count"],
        "total_count": report["total_count"],
        "required_adapters": sorted(required),
        "adapters": report["adapters"],
        "failures": failures,
        "known_gaps": report["known_gaps"],
        "pass": passed,
        "pass_criteria": "All required adapters available AND running on Raspberry Pi hardware.",
    }


def _run_gate_stub(gate: str, node_config: dict[str, Any], soak_minutes: float) -> dict[str, Any]:
    """Delegate G2-G5 to validation/run_gate.py for full instructions."""
    return {
        "codename": "SENTRY",
        "gate": gate,
        "note": f"Run the full gate harness: python validation/run_gate.py --gate {gate}",
        "see": "docs/gate_execution.md",
        "pass": False,
        "manual_confirm_required": True,
    }


def run_simulation(
    scenario_name: str,
    duration_s: float,
    rate_hz: float,
    node_id: str,
    mission_path: Path,
    output_dir: Path,
    seed: int,
    validate_schemas: bool = True,
) -> dict[str, Any]:
    mission = _load_json(mission_path)
    guardian = SentryGuardian(node_id, mission)
    audit = AuditLogger()
    store = AuditStore(AuditStoreConfig(path=output_dir / f"sentry_sim_{scenario_name}.db"))
    scenario = scenario_from_name(scenario_name)
    sensors = SimulatedSensorArray(node_id, scenario, rng_seed=seed)
    power = PowerMetrics(PowerMetricsConfig(target_avg_watts=5.0))

    output_dir.mkdir(parents=True, exist_ok=True)
    alerts_path = output_dir / f"sentry_sim_{scenario_name}.jsonl"
    audit_path = output_dir / f"sentry_audit_{scenario_name}.jsonl"

    alert_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    max_level = "CLEAR"
    level_rank = {"CLEAR": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3, "HOLD": 4}

    for event in sensors.stream(duration_s, rate_hz):
        power.record(duty_active=True, rtl_active=True, acoustic_active=True)
        event_dict = event.to_dict()
        if validate_schemas:
            validate(event_dict, "sensor_event.v1.json")

        alert = guardian.process(event)
        alert_dict = alert.to_dict()
        store.append("alert", alert_dict, timestamp_s=event.timestamp_s)
        if validate_schemas:
            validate(alert_dict, "alert_frame.v1.json")

        audit_entry = None
        if alert.level in {"ORANGE", "RED", "HOLD"}:
            audit_entry = audit.append("alert", alert_dict, timestamp_s=event.timestamp_s)
            if validate_schemas:
                validate(audit_entry, "audit_entry.v1.json")

        alert_rows.append(alert_dict)
        if audit_entry is not None:
            audit_rows.append(audit_entry)

        if level_rank[alert.level] > level_rank[max_level]:
            max_level = alert.level

        LOG.info(
            "seq=%d level=%s score=%.3f state=%s",
            alert.seq,
            alert.level,
            alert.threat_score,
            alert.guardian_state,
        )

    alerts_path.write_text(
        "\n".join(json.dumps(r) for r in alert_rows) + "\n", encoding="utf-8"
    )
    audit_text = "\n".join(json.dumps(r) for r in audit_rows)
    audit_path.write_text((audit_text + "\n") if audit_text else "", encoding="utf-8")

    chain_ok = audit.verify_chain(audit_rows)
    summary = {
        "codename": "SENTRY",
        "scenario": scenario_name,
        "frames": len(alert_rows),
        "max_level": max_level,
        "audit_chain_valid": chain_ok,
        "sqlite_path": str(store.config.path),
        "power": power.summary(),
        "alerts_path": str(alerts_path),
        "audit_path": str(audit_path),
    }
    LOG.info("simulation complete: %s", json.dumps(summary))
    return summary


def sim_main() -> int:
    root = _repo_root()
    parser = argparse.ArgumentParser(description="SENTRY simulation runner")
    parser.add_argument("--scenario", default="intrusion", choices=["benign", "intrusion", "jamming", "low_visibility"])
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--rate-hz", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--gpu", action="store_true", help="RunPod: GPU batch FFT + Monte Carlo before CPU sim")
    parser.add_argument("--node-id", default="sentry-pi-001")
    parser.add_argument("--mission", type=Path, default=root / "configs" / "sentry_mission_profile.json")
    parser.add_argument("--output", type=Path, default=root / "validation" / "reports")
    args = parser.parse_args()

    _setup_logging()
    if args.gpu:
        import json as _json
        import os

        os.environ["SENTRY_FORCE_GPU"] = "1"
        from sentry.gpu.acoustic_batch import gpu_batch_fft_propeller
        from sentry.gpu.monte_carlo import gpu_monte_carlo_fusion
        from sentry.gpu.melt import sample_gpu_utilization

        LOG.info("SENTRY --gpu: RunPod melt pre-pass (NOT for Pi field)")
        fft = gpu_batch_fft_propeller()
        mc = gpu_monte_carlo_fusion(total=500_000)
        util = sample_gpu_utilization()
        pre = {"fft": fft.__dict__, "monte_carlo": mc.__dict__, "gpu_util": util}
        print(_json.dumps({"codename": "SENTRY", "gpu_pre_pass": pre}))

    summary = run_simulation(
        scenario_name=args.scenario,
        duration_s=args.duration,
        rate_hz=args.rate_hz,
        node_id=args.node_id,
        mission_path=args.mission,
        output_dir=args.output,
        seed=args.seed,
    )
    print(json.dumps(summary))
    return 0 if summary["audit_chain_valid"] else 1


def guard_main() -> int:
    root = _repo_root()
    parser = argparse.ArgumentParser(description="SENTRY guardian — demo, probe, or live ingest")
    parser.add_argument("--demo", action="store_true", help="Run one intrusion sample")
    parser.add_argument("--probe", action="store_true", help="Probe Pi hardware adapters (G1 BIT)")
    parser.add_argument("--gate", choices=["G1", "G2", "G3", "G4", "G5"], help="Run a physical acceptance gate")
    parser.add_argument("--soak-minutes", type=float, default=480.0, help="G5 soak duration")
    parser.add_argument("--live", action="store_true", help="Continuous live ingest with simulation fallback")
    parser.add_argument("--failure-modes", action="store_true", help="Run failure mode simulation suite")
    parser.add_argument("--duration", type=float, default=None, help="Live ingest duration (omit for service loop)")
    parser.add_argument("--rate-hz", type=float, default=0.5)
    parser.add_argument("--node-id", default="sentry-pi-001")
    parser.add_argument("--mission", type=Path, default=root / "configs" / "sentry_mission_profile.json")
    parser.add_argument("--node-config", type=Path, default=root / "configs" / "sentry_node_config.json")
    parser.add_argument("--output", type=Path, default=root / "validation" / "reports")
    args = parser.parse_args()

    _setup_logging()

    if args.gate:
        from sentry.hardware.probe import probe_all  # noqa: F401

        gate = args.gate
        node_config = _load_json(args.node_config)
        report = _run_g1_report(node_config) if gate == "G1" else _run_gate_stub(gate, node_config, args.soak_minutes)
        print(json.dumps(report, indent=2))
        return 0 if report.get("pass") else 1

    if args.probe:
        node_config = _load_json(args.node_config)
        report = _run_g1_report(node_config)
        print(json.dumps(report, indent=2))
        return 0 if report.get("pass") else 1

    if args.failure_modes:
        report = run_failure_modes()
        print(json.dumps(report))
        return 0 if report["overall"] == "PASS" else 1

    if args.live:
        mission = _load_json(args.mission)
        node_config = _load_json(args.node_config)
        summary = run_live_ingest(
            node_id=args.node_id,
            mission=mission,
            node_config=node_config,
            duration_s=args.duration,
            rate_hz=args.rate_hz,
            output_dir=args.output,
        )
        print(json.dumps(summary))
        return 0

    if args.demo:
        mission = _load_json(args.mission)
        guardian = SentryGuardian(args.node_id, mission)
        scenario = scenario_from_name("intrusion")
        sensors = SimulatedSensorArray(args.node_id, scenario, rng_seed=42)
        event = sensors.sample(10.0)
        alert = guardian.process(event)
        print(json.dumps(alert.to_dict(), indent=2))
        return 0

    print("Provide --demo, --probe, --live, or --failure-modes", file=sys.stderr)
    return 1


def melt_main() -> int:
    """RunPod GPU melt — force high CUDA utilization."""
    import os

    os.environ.setdefault("SENTRY_FORCE_GPU", "1")
    from sentry.simulation.stress_test import main as stress_main

    return stress_main()


def deploy_main() -> int:
    """Mechanical chain deployment simulation (no explosives)."""
    root = _repo_root()
    parser = argparse.ArgumentParser(description="SENTRY chain deployment simulator")
    parser.add_argument("--config", type=Path, default=root / "configs" / "deployment_chain_alpha.json")
    parser.add_argument("--monte-carlo", action="store_true", help="Run impact/join Monte Carlo")
    parser.add_argument("--total", type=int, default=50_000)
    parser.add_argument("--gpu", action="store_true", help="Force CUDA for Monte Carlo (RunPod)")
    parser.add_argument("--compare-line-charge", action="store_true", help="Include line-charge reference (destructive)")
    parser.add_argument("--output", type=Path, default=root / "validation" / "reports" / "deployment-chain.json")
    args = parser.parse_args()

    _setup_logging()
    import os

    cfg_data = _load_json(args.config)
    dep = cfg_data.get("deployment", cfg_data)
    chain_id = str(cfg_data.get("chain_id", "CHAIN-ALPHA"))

    mission = {"deployment": {"enabled": True, **dep}}
    guardian = SentryGuardian("sentry-chain-000", mission)
    audit = AuditLogger()

    report: dict[str, Any] = {
        "codename": "SENTRY",
        "type_designation": cfg_data.get("type_designation", "AN/GSQ-100(V)1"),
        "chain_id": chain_id,
        "mode": "defensive-only",
        "launch_method": dep.get("launch_method", "pneumatic_soft"),
    }

    sequence = guardian.run_deployment_sequence()
    report["deployment_sequence"] = sequence
    audit.append("deployment_sequence", sequence)

    if args.monte_carlo:
        if args.gpu:
            os.environ["SENTRY_FORCE_GPU"] = "1"
        from sentry.deployment.config import ChainDeploymentConfig
        from sentry.deployment.monte_carlo_impact import gpu_monte_carlo_deployment

        mc = gpu_monte_carlo_deployment(
            total=args.total,
            config=ChainDeploymentConfig.from_dict(dep),
            method=dep.get("launch_method", "pneumatic_soft"),
        )
        report["monte_carlo"] = mc.to_dict()
        audit.append("deployment_monte_carlo", report["monte_carlo"])

    if args.compare_line_charge:
        from sentry.deployment.config import ChainDeploymentConfig
        from sentry.deployment.physics import simulate_line_deployment

        lc = simulate_line_deployment(
            ChainDeploymentConfig.from_dict({**dep, "launch_method": "line_charge_reference"})
        )
        report["line_charge_reference"] = lc.to_dict()
        audit.append("line_charge_reference", report["line_charge_reference"])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if sequence.get("operational") or not args.monte_carlo else 0


if __name__ == "__main__":
    sys.exit(sim_main())
