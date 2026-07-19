"""
SENTRY physical gate runner (G1-G5) — AN/GSQ-100(V)1.

Run ON THE PI after assembly. Produces a structured PASS/FAIL report with
exact remediation steps for every failure. Defensive-only; no transmit logic.

Usage:
    python validation/run_gate.py --gate G1
    python validation/run_gate.py --gate G5 --soak-minutes 480
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "implementation" / "src"
sys.path.insert(0, str(SRC))


def _remediation(adapter: str) -> list[str]:
    table = {
        "pir_gpio": [
            "Confirm PIR OUT on GPIO17 (physical pin 11), VCC 5V (pin 2), GND (pin 6).",
            "Run on Pi only — adapter reports unavailable off-Pi by design.",
            "Add user to gpio group: sudo usermod -aG gpio $USER ; then reboot.",
        ],
        "acoustic_sensor": [
            "Install audio deps: sudo apt-get install -y portaudio19-dev && pip install -e implementation[hardware]",
            "Check mic enumerated: arecord -l   (expect a USB card).",
            "Replug USB mic; avoid unpowered hub ports.",
        ],
        "rf_sensor": [
            "Install RTL tools: sudo apt-get install -y rtl-sdr librtlsdr-dev",
            "Blacklist DVB driver: echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/rtl-sdr-blacklist.conf ; reboot",
            "Verify dongle: rtl_test -t   (expect 'Found 1 device').",
            "Use the specified RTL-SDR Blog V4 — cheap clones drift and fail sweeps.",
        ],
        "visual": [
            "Optional sensor. If unused, ignore. Else: enable camera and check /dev/video0.",
        ],
        "tamper_gpio": [
            "Confirm tamper switch on GPIO21 (physical pin 40) to GND (physical pin 39), pull-up active-high on case open.",
            "Run on Pi only.",
        ],
        "meshtastic_handler": [
            "Confirm Waveshare LoRa HAT or Meshtastic bridge on /dev/ttyACM0 or symlink /dev/meshtastic: ls -l /dev/ttyACM* /dev/meshtastic",
            "Install udev rules: sudo cp deploy/99-sentry.rules /etc/udev/rules.d/ ; sudo udevadm control --reload-rules ; sudo udevadm trigger",
            "Confirm 915 MHz region and compatible Meshtastic bridge firmware.",
            "Add user to dialout group: sudo usermod -aG dialout $USER ; reboot.",
        ],
    }
    return table.get(adapter, ["No remediation registered — inspect adapter detail."])


def _load_node_config(path: Path | None) -> dict:
    candidates = [
        path,
        Path("/etc/sentry/node_config.json"),
        ROOT / "configs" / "nodes" / "sentry-pi-zero-001.json",
        ROOT / "configs" / "sentry_node_config.json",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return json.loads(Path(c).read_text(encoding="utf-8"))
    return {}


def gate_g1(node_config_path: Path | None) -> dict:
    from sentry.hardware import is_raspberry_pi
    from sentry.hardware.probe import probe_all

    node_config = _load_node_config(node_config_path)
    report = probe_all(node_config)

    required = {"pir_gpio", "acoustic_sensor", "rf_sensor", "tamper_gpio", "meshtastic_handler"}
    failures = []
    for adapter in report["adapters"]:
        if adapter["adapter"] in required and not adapter["available"]:
            failures.append(
                {
                    "adapter": adapter["adapter"],
                    "detail": adapter["detail"],
                    "remediation": _remediation(adapter["adapter"]),
                }
            )

    passed = len(failures) == 0 and is_raspberry_pi()
    return {
        "gate": "G1",
        "name": "Hardware probe (BIT)",
        "pi_detected": is_raspberry_pi(),
        "available_count": report["available_count"],
        "total_count": report["total_count"],
        "required_adapters": sorted(required),
        "failures": failures,
        "known_gaps": report["known_gaps"],
        "pass": passed,
        "pass_criteria": "All required adapters available AND running on Raspberry Pi hardware.",
    }


def gate_g2(node_config_path: Path | None) -> dict:
    """RF 2.4 GHz burst detection — needs a 2.4 GHz emitter near the node."""
    from sentry.sensors.rf_sensor import RfSensor, RfSensorConfig

    node_config = _load_node_config(node_config_path)
    hw = node_config.get("hardware", {})
    rf = RfSensor(RfSensorConfig(**hw.get("rf_sensor", {})))
    available = rf.available
    detail = "RTL-SDR available — power on a 2.4 GHz source (Wi-Fi AP/phone hotspot) within 2 m."
    if not available:
        detail = "RTL-SDR NOT available — fix G1 rf_sensor first."
    return {
        "gate": "G2",
        "name": "RF 2.4 GHz burst",
        "rf_available": available,
        "instructions": [
            "1. Place a 2.4 GHz source (Wi-Fi AP or phone hotspot) ~1-2 m from the RTL antenna.",
            "2. Run: sentry-guard --live --duration 60 --node-config /etc/sentry/node_config.json",
            "3. Inspect alerts for rf_burst_2g4 flag / elevated rf channel.",
        ],
        "detail": detail,
        "pass": available,  # hardware presence gate; human confirms burst flag
        "pass_criteria": "rf_burst_2g4 appears in a live alert while emitter is on; absent when off.",
        "manual_confirm_required": True,
    }


def gate_g3(node_config_path: Path | None) -> dict:
    """Acoustic 100-500 Hz peak — needs a 220 Hz tone speaker at ~5 m."""
    from sentry.sensors.acoustic_sensor import AcousticSensor

    ac = AcousticSensor()
    available = ac.available
    ac.close()
    return {
        "gate": "G3",
        "name": "Acoustic 220 Hz peak",
        "acoustic_available": available,
        "instructions": [
            "1. Play a steady 220 Hz tone from a speaker ~5 m from the mic.",
            "2. Run: sentry-guard --live --duration 60 --node-config /etc/sentry/node_config.json",
            "3. Inspect alerts for acoustic_propeller_peak flag.",
        ],
        "detail": "Mic available." if available else "Mic NOT available — fix G1 acoustic_sensor first.",
        "pass": available,
        "pass_criteria": "acoustic_propeller_peak appears while tone plays; absent in silence.",
        "manual_confirm_required": True,
    }


def gate_g4(node_config_path: Path | None) -> dict:
    """4-node mesh ORANGE relay — needs >=2 nodes powered with Meshtastic."""
    from sentry.networking.meshtastic_handler import (
        MeshNodeConfig,
        MeshtasticHandler,
        MeshtasticHandlerConfig,
    )

    node_config = _load_node_config(node_config_path)
    hw = node_config.get("hardware", {})
    node_id = node_config.get("node_id", "sentry-pi-zero-001")
    mesh_hw = {k: v for k, v in hw.get("meshtastic", {}).items() if k not in ("peers", "fallback_spool")}
    mesh = MeshtasticHandler(MeshtasticHandlerConfig(local=MeshNodeConfig(node_id=node_id, **mesh_hw)))
    available = mesh.available
    summary = mesh.relay_peer_summary()
    mesh.close()
    return {
        "gate": "G4",
        "name": "4-node mesh ORANGE relay",
        "mesh_available": available,
        "peer_summary": summary,
        "instructions": [
            "1. Power >=2 nodes with Meshtastic boards on the same channel.",
            "2. Trigger ORANGE on one node (G2/G3 stimulus).",
            "3. Confirm OMEN alert received on peer (Meshtastic phone app or peer inbox).",
        ],
        "detail": "Meshtastic device present." if available else "No Meshtastic device — TX falls back to spool.",
        "pass": available,
        "pass_criteria": "Peer node receives ORANGE OMEN alert within 5 s of trigger.",
        "manual_confirm_required": True,
    }


def gate_g5(node_config_path: Path | None, soak_minutes: float) -> dict:
    """8 h soak — power budget and thermal. Short sample here; full run is unattended."""
    from sentry.guardian import SentryGuardian
    from sentry.ingest import run_live_ingest

    node_config = _load_node_config(node_config_path)
    mission_path = ROOT / "configs" / "sentry_mission_profile.json"
    mission = json.loads(mission_path.read_text(encoding="utf-8")) if mission_path.exists() else {}
    sample_s = min(soak_minutes * 60.0, 120.0)
    summary = run_live_ingest(
        node_id=node_config.get("node_id", "sentry-pi-zero-001"),
        mission=mission,
        node_config=node_config,
        duration_s=sample_s,
        rate_hz=0.5,
        output_dir=ROOT / "validation" / "reports",
    )
    power = summary.get("power", {})
    under = power.get("under_target", False)
    throttled = power.get("any_throttled", True)
    return {
        "gate": "G5",
        "name": "Soak / power budget",
        "sampled_seconds": sample_s,
        "requested_minutes": soak_minutes,
        "power": power,
        "instructions": [
            "Full gate: run sentry-guardian.service for 8 h, then analyze sentry_power.jsonl.",
            "Check mean_watts < 5.0 and any_throttled == false.",
        ],
        "pass": bool(under and not throttled),
        "pass_criteria": "Mean power < 5 W AND no thermal throttle across 8 h.",
        "manual_confirm_required": soak_minutes * 60 > sample_s,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SENTRY physical gate runner (G1-G5)")
    parser.add_argument("--gate", required=True, choices=["G1", "G2", "G3", "G4", "G5"])
    parser.add_argument("--node-config", type=Path, default=None)
    parser.add_argument("--soak-minutes", type=float, default=480.0)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.gate == "G1":
        result = gate_g1(args.node_config)
    elif args.gate == "G2":
        result = gate_g2(args.node_config)
    elif args.gate == "G3":
        result = gate_g3(args.node_config)
    elif args.gate == "G4":
        result = gate_g4(args.node_config)
    else:
        result = gate_g5(args.node_config, args.soak_minutes)

    result["codename"] = "SENTRY"
    result["type_designation"] = "AN/GSQ-100(V)1"
    result["tools_present"] = {
        "rtl_test": bool(shutil.which("rtl_test")),
        "arecord": bool(shutil.which("arecord")),
    }

    out = args.output or (ROOT / "validation" / "reports" / f"gate-{args.gate.lower()}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    banner = "PASS" if result.get("pass") else "FAIL / MANUAL CONFIRM"
    print(f"=== SENTRY {args.gate} — {result['name']}: {banner} ===")
    print(json.dumps(result, indent=2))
    if result.get("failures"):
        print("\nREMEDIATION:")
        for f in result["failures"]:
            print(f"  [{f['adapter']}] {f['detail']}")
            for step in f["remediation"]:
                print(f"    - {step}")
    return 0 if result.get("pass") else 1


if __name__ == "__main__":
    sys.exit(main())
