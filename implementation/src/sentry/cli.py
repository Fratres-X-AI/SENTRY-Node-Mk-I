"""CLI entrypoints for SENTRY guard and simulation."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from sentry.audit import AuditLogger
from sentry.failure_modes import run_all as run_failure_modes
from sentry.guardian import SentryGuardian
from sentry.hardware.probe import probe_all
from sentry.ingest import run_live_ingest
from sentry.sensors.power_metrics import PowerMetrics, PowerMetricsConfig
from sentry.schema_validate import validate
from sentry.simulation.synthetic import SimulatedSensorArray, scenario_from_name

LOG = logging.getLogger("SENTRY")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _setup_logging(prefix: str = "SENTRY") -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{prefix}] %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def run_simulation(
    scenario_name: str,
    duration_s: float,
    rate_hz: float,
    node_id: str,
    mission_path: Path,
    output_dir: Path,
    seed: int,
    validate_schemas: bool = True,
) -> dict:
    mission = _load_json(mission_path)
    guardian = SentryGuardian(node_id, mission)
    audit = AuditLogger()
    scenario = scenario_from_name(scenario_name)
    sensors = SimulatedSensorArray(node_id, scenario, rng_seed=seed)
    power = PowerMetrics(PowerMetricsConfig(target_avg_watts=5.0))

    output_dir.mkdir(parents=True, exist_ok=True)
    alerts_path = output_dir / f"sentry_sim_{scenario_name}.jsonl"
    audit_path = output_dir / f"sentry_audit_{scenario_name}.jsonl"

    alert_rows: list[dict] = []
    audit_rows: list[dict] = []
    max_level = "CLEAR"
    level_rank = {"CLEAR": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3, "HOLD": 4}

    for event in sensors.stream(duration_s, rate_hz):
        power.record(duty_active=True, rtl_active=True, acoustic_active=True)
        event_dict = event.to_dict()
        if validate_schemas:
            validate(event_dict, "sensor_event.v1.json")

        alert = guardian.process(event)
        alert_dict = alert.to_dict()
        if validate_schemas:
            validate(alert_dict, "alert_frame.v1.json")

        audit_entry = audit.append("alert", alert_dict, timestamp_s=event.timestamp_s)
        if validate_schemas:
            validate(audit_entry, "audit_entry.v1.json")

        alert_rows.append(alert_dict)
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
    audit_path.write_text(
        "\n".join(json.dumps(r) for r in audit_rows) + "\n", encoding="utf-8"
    )

    chain_ok = audit.verify_chain(audit_rows)
    summary = {
        "codename": "SENTRY",
        "scenario": scenario_name,
        "frames": len(alert_rows),
        "max_level": max_level,
        "audit_chain_valid": chain_ok,
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
    parser.add_argument("--probe", action="store_true", help="Probe Pi hardware adapters")
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

    if args.probe:
        node_config = _load_json(args.node_config)
        report = probe_all(node_config)
        print(json.dumps(report, indent=2))
        return 0

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


if __name__ == "__main__":
    sys.exit(sim_main())
