"""Simulated passive sensor feeds for desktop and Pi fallback."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterator

from sentry.types import SensorChannels, SensorEvent


@dataclass
class SimScenario:
    name: str
    base_pir: float = 0.05
    base_acoustic: float = 0.08
    base_rf: float = 0.04
    base_visual: float = 0.06
    intrusion_start_s: float | None = None
    intrusion_peak_s: float | None = None
    jamming_start_s: float | None = None
    low_visibility: bool = False
    propeller_tone_hz: float = 180.0


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _intrusion_ramp(t: float, start: float, peak: float) -> float:
    if t < start:
        return 0.0
    if t >= peak:
        return 1.0
    return (t - start) / max(peak - start, 1e-6)


class SimulatedSensorArray:
    """Generates deterministic synthetic sensor_event.v1 frames."""

    def __init__(self, node_id: str, scenario: SimScenario, rng_seed: int = 42) -> None:
        self.node_id = node_id
        self.scenario = scenario
        self._rng = random.Random(rng_seed)
        self._seq = 0

    def sample(self, timestamp_s: float) -> SensorEvent:
        s = self.scenario

        def noise(scale: float) -> float:
            return self._rng.uniform(-scale, scale)

        intrusion = 0.0
        if s.intrusion_start_s is not None and s.intrusion_peak_s is not None:
            intrusion = _intrusion_ramp(timestamp_s, s.intrusion_start_s, s.intrusion_peak_s)

        jamming = s.jamming_start_s is not None and timestamp_s >= s.jamming_start_s
        vis_scale = 0.35 if s.low_visibility else 1.0

        # Propeller-like acoustic bump during intrusion (100-500 Hz band)
        propeller = intrusion * 0.75 if 100 <= s.propeller_tone_hz <= 500 else 0.0

        channels = SensorChannels(
            pir=_clamp(s.base_pir + intrusion * 0.85 + noise(0.04)),
            acoustic=_clamp(s.base_acoustic + propeller + noise(0.05)),
            rf=_clamp(s.base_rf + (0.98 if jamming else intrusion * 0.40) + noise(0.02)),
            visual=_clamp((s.base_visual + intrusion * 0.80 + noise(0.04)) * vis_scale),
        )

        flags: dict[str, bool] = {
            "jamming_suspected": jamming,
            "low_visibility": s.low_visibility,
            "rf_burst_2g4": intrusion > 0.5 and not jamming,
            "rf_burst_5g8": False,
            "acoustic_propeller_peak": propeller > 0.3,
        }

        event = SensorEvent(
            node_id=self.node_id,
            seq=self._seq,
            timestamp_s=timestamp_s,
            channels=channels,
            flags=flags,
        )
        self._seq += 1
        return event

    def stream(self, duration_s: float, rate_hz: float) -> Iterator[SensorEvent]:
        dt = 1.0 / rate_hz
        t = 0.0
        while t <= duration_s + 1e-9:
            yield self.sample(t)
            t += dt


def scenario_from_name(name: str) -> SimScenario:
    mapping = {
        "benign": SimScenario(name="benign"),
        "intrusion": SimScenario(
            name="intrusion",
            intrusion_start_s=5.0,
            intrusion_peak_s=12.0,
            propeller_tone_hz=220.0,
        ),
        "jamming": SimScenario(
            name="jamming",
            intrusion_start_s=4.0,
            intrusion_peak_s=10.0,
            jamming_start_s=8.0,
        ),
        "low_visibility": SimScenario(
            name="low_visibility",
            low_visibility=True,
            intrusion_start_s=6.0,
            intrusion_peak_s=14.0,
        ),
    }
    if name not in mapping:
        raise ValueError(f"unknown scenario: {name}")
    return mapping[name]
