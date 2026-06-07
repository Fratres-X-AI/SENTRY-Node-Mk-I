"""Continuous live ingest loop for SENTRY guardian service."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from sentry.audit import AuditLogger
from sentry.guardian import SentryGuardian
from sentry.hardware.live_array import LiveSensorArray
from sentry.sensors.power_metrics import PowerMetrics, PowerMetricsConfig
from sentry.schema_validate import validate
from sentry.tamper_response import TamperWipeConfig, handle_tamper

LOG = logging.getLogger("SENTRY")


def run_live_ingest(
    node_id: str,
    mission: dict[str, Any],
    node_config: dict[str, Any],
    duration_s: float | None = None,
    rate_hz: float = 0.5,
    output_dir: Path | None = None,
    validate_schemas: bool = True,
) -> dict[str, Any]:
    power_cfg = node_config.get("power", {})
    log_path = Path(power_cfg["log_path"]) if power_cfg.get("log_path") else None
    power = PowerMetrics(
        PowerMetricsConfig(
            log_path=log_path,
            target_avg_watts=float(power_cfg.get("target_avg_watts", 5.0)),
        )
    )
    guardian = SentryGuardian(node_id, mission, power_metrics=power)
    audit = AuditLogger()
    array = LiveSensorArray(node_id, node_config)
    mesh = array.relay

    output_dir = output_dir or Path(node_config.get("outputs", {}).get("alert_dir", "validation/reports"))
    output_dir.mkdir(parents=True, exist_ok=True)
    alerts_path = output_dir / "sentry_live_alerts.jsonl"
    audit_path = output_dir / "sentry_live_audit.jsonl"

    dt = 1.0 / rate_hz
    t0 = time.time()
    frames = 0
    max_level = "CLEAR"
    rank = {"CLEAR": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3, "HOLD": 4}
    tamper_cfg = TamperWipeConfig(**node_config.get("tamper_response", {"dry_run": True}))

    audit.append("boot", {"node_id": node_id, "mode": "live_ingest"}, timestamp_s=t0)
    fallback = array.fallback_report()

    try:
        while True:
            if duration_s is not None and (time.time() - t0) >= duration_s:
                break

            event = array.sample(time.time())

            if event.flags.get("tamper_detected"):
                handle_tamper(audit, tamper_cfg, timestamp_s=event.timestamp_s)

            if validate_schemas:
                validate(event.to_dict(), "sensor_event.v1.json")

            alert = guardian.process(event)
            alert_dict = alert.to_dict()

            if validate_schemas:
                validate(alert_dict, "alert_frame.v1.json")

            entry = audit.append("alert", alert_dict, timestamp_s=event.timestamp_s)
            if validate_schemas:
                validate(entry, "audit_entry.v1.json")

            with alerts_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(alert_dict) + "\n")
            with audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")

            if alert.level in {"ORANGE", "RED", "HOLD"}:
                mesh.send_alert(alert_dict)

            if rank[alert.level] > rank[max_level]:
                max_level = alert.level

            LOG.info(
                "SENTRY live seq=%d level=%s score=%.3f fallback=%s",
                alert.seq,
                alert.level,
                alert.threat_score,
                event.flags.get("fallback_channels"),
            )
            frames += 1
            time.sleep(dt)
    finally:
        array.close()

    power_summary = guardian.power_summary()
    return {
        "codename": "SENTRY",
        "mode": "live_ingest",
        "frames": frames,
        "max_level": max_level,
        "fallback": fallback,
        "power": power_summary,
        "mesh": mesh.relay_peer_summary(),
        "alerts_path": str(alerts_path),
        "audit_path": str(audit_path),
    }
