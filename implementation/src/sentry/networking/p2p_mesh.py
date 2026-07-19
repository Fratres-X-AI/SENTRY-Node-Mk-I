"""Compact signed intel summaries for Meshtastic relay."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any


def _mesh_secret() -> bytes:
    raw = os.environ.get("SENTRY_MESH_SIGN_KEY") or os.environ.get("SENTRY_AUDIT_HMAC_KEY")
    if raw is None:
        raw = "sentry-dev-key"
    if os.environ.get("SENTRY_ENV", "").lower() == "production" and raw == "sentry-dev-key":
        raise RuntimeError("default mesh signing key is not allowed in production")
    return raw.encode("utf-8")


def _canonical(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@dataclass
class IntelSummary:
    node_id: str
    level: str
    threat_score: float
    seq: int
    timestamp_s: float
    passive_flags: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": "sentry_intel_summary.v1",
            "node_id": self.node_id,
            "level": self.level,
            "threat_score": round(self.threat_score, 3),
            "seq": self.seq,
            "timestamp_s": self.timestamp_s,
            "passive_flags": self.passive_flags,
        }


def build_intel_summary(alert: dict[str, Any]) -> dict[str, Any]:
    event_flags = alert.get("sensor_event", {}).get("flags", {})
    passive_flags = {
        key: value
        for key, value in event_flags.items()
        if key in {"passive_network_anomaly", "steganography_suspected", "ghost_monitor_score", "whisper_entropy"}
    }
    summary = IntelSummary(
        node_id=str(alert.get("node_id", "")),
        level=str(alert.get("level", "")),
        threat_score=float(alert.get("threat_score", 0.0)),
        seq=int(alert.get("seq", 0)),
        timestamp_s=float(alert.get("timestamp_s", 0.0)),
        passive_flags=passive_flags,
    ).to_payload()
    summary["sig"] = sign_summary(summary)
    return summary


def sign_summary(summary: dict[str, Any]) -> str:
    payload = {key: value for key, value in summary.items() if key != "sig"}
    return hmac.new(_mesh_secret(), _canonical(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def verify_summary(summary: dict[str, Any]) -> bool:
    sig = str(summary.get("sig", ""))
    if not sig:
        return False
    return hmac.compare_digest(sig, sign_summary(summary))
