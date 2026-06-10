"""Shared types for SENTRY pipeline stages."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SensorChannels:
    pir: float
    acoustic: float
    rf: float
    visual: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class SensorEvent:
    node_id: str
    seq: int
    timestamp_s: float
    channels: SensorChannels
    flags: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "sensor_event.v1",
            "codename": "SENTRY",
            "node_id": self.node_id,
            "seq": self.seq,
            "timestamp_s": self.timestamp_s,
            "channels": self.channels.to_dict(),
            "flags": self.flags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SensorEvent:
        ch = data["channels"]
        return cls(
            node_id=data["node_id"],
            seq=int(data["seq"]),
            timestamp_s=float(data["timestamp_s"]),
            channels=SensorChannels(
                pir=float(ch["pir"]),
                acoustic=float(ch["acoustic"]),
                rf=float(ch["rf"]),
                visual=float(ch["visual"]),
            ),
            flags=dict(data.get("flags", {})),
        )


@dataclass
class AlertFrame:
    node_id: str
    seq: int
    timestamp_s: float
    level: str
    threat_score: float
    rationale: str
    guardian_state: str
    sensor_event: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "alert_frame.v1",
            "codename": "SENTRY",
            "node_id": self.node_id,
            "seq": self.seq,
            "timestamp_s": self.timestamp_s,
            "level": self.level,
            "threat_score": self.threat_score,
            "rationale": self.rationale,
            "guardian_state": self.guardian_state,
            "sensor_event": self.sensor_event,
        }


AlertLevel = str  # CLEAR | YELLOW | ORANGE | RED | HOLD
