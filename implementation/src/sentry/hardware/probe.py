"""Probe all SENTRY hardware adapters and sensor drivers."""

from __future__ import annotations

from typing import Any

from sentry.hardware.pir import probe as pir_probe
from sentry.hardware.tamper import probe as tamper_probe
from sentry.hardware.visual import probe as visual_probe
from sentry.networking.meshtastic_handler import MeshtasticHandler, MeshtasticHandlerConfig, MeshNodeConfig
from sentry.sensors.acoustic_sensor import AcousticSensor
from sentry.sensors.rf_sensor import RfSensor, RfSensorConfig


def probe_all(node_config: dict[str, Any] | None = None) -> dict[str, Any]:
    node_config = node_config or {}
    hw = node_config.get("hardware", {})
    node_id = node_config.get("node_id", "sentry-pi-zero-001")

    rf = RfSensor(RfSensorConfig(**hw.get("rf_sensor", hw.get("rf_rtl", {}))))
    acoustic = AcousticSensor()
    mesh_hw = {k: v for k, v in hw.get("meshtastic", {}).items() if k not in ("peers", "fallback_spool")}
    mesh = MeshtasticHandler(
        MeshtasticHandlerConfig(local=MeshNodeConfig(node_id=node_id, **mesh_hw))
    )

    adapters = [
        pir_probe(),
        acoustic.probe(),
        rf.probe(),
        visual_probe(),
        tamper_probe(),
        mesh.probe(),
    ]
    mesh.close()
    acoustic.close()

    gaps = [
        "RTL-SDR V3 cannot tune 5.8 GHz — 5g8 band uses synthetic fallback",
        "Field FP/FN rates unvalidated",
        "Meshtastic RX hook is spool-based placeholder",
    ]

    available = sum(1 for a in adapters if a["available"])
    return {
        "codename": "SENTRY",
        "adapters": adapters,
        "available_count": available,
        "total_count": len(adapters),
        "hardware_profile": hw.get("profile", "unknown"),
        "known_gaps": gaps,
    }
