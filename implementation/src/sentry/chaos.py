"""Malformed/flood input handling for pre-physical chaos tests."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sentry.types import SensorEvent


@dataclass
class ChaosParseReport:
    accepted: int = 0
    malformed: int = 0
    rejected: int = 0
    window_size: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "accepted": self.accepted,
            "malformed": self.malformed,
            "rejected": self.rejected,
            "window_size": self.window_size,
        }


@dataclass
class ChaosStreamParser:
    max_window: int = 500
    window: deque[SensorEvent] = field(init=False)

    def __post_init__(self) -> None:
        self.window = deque(maxlen=self.max_window)

    def parse_line(self, line: str) -> SensorEvent | None:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        try:
            event = _event_from_chaos_payload(obj)
        except (KeyError, TypeError, ValueError):
            return None
        self.window.append(event)
        return event

    def parse_file(self, path: Path) -> ChaosParseReport:
        report = ChaosParseReport()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            before = len(self.window)
            event = self.parse_line(line)
            if event is not None:
                report.accepted += 1
            elif before == len(self.window):
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    report.malformed += 1
                else:
                    report.rejected += 1
        report.window_size = len(self.window)
        return report


def _bounded(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    numeric = float(value)
    return max(low, min(high, numeric))


def _event_from_chaos_payload(obj: dict[str, Any]) -> SensorEvent:
    metrics = obj["metrics"]
    rf_2g4 = float(metrics["rf_2g4_dbm"])
    rf_5g8 = float(metrics.get("rf_5g8_dbm", rf_2g4))
    acoustic_hz = float(metrics.get("acoustic_fft_peak_hz", 0.0))
    rf_score = _bounded((max(rf_2g4, rf_5g8) + 100.0) / 90.0)
    acoustic_score = 0.8 if 100.0 <= acoustic_hz <= 500.0 else 0.0
    jamming = rf_2g4 >= 0.0 or rf_5g8 >= 0.0
    return SensorEvent.from_dict(
        {
            "node_id": str(obj["node_id"]),
            "seq": int(obj["sequence_id"]),
            "timestamp_s": 0.0,
            "channels": {"pir": 0.0, "acoustic": acoustic_score, "rf": rf_score, "visual": 0.0},
            "flags": {
                "jamming_suspected": jamming,
                "rf_burst_2g4": rf_score > 0.75 and not jamming,
                "rf_burst_5g8": False,
                "acoustic_propeller_peak": acoustic_score > 0.0,
                "passive_score": 0.0,
            },
        }
    )
