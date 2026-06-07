"""Live hardware sensor array — uses sentry.sensors drivers + simulation fallback."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Iterator

from sentry.hardware.pir import PirAdapter, PirConfig
from sentry.hardware.tamper import TamperAdapter, TamperConfig
from sentry.hardware.visual import VisualAdapter, VisualConfig
from sentry.networking.meshtastic_handler import MeshNodeConfig, MeshtasticHandler, MeshtasticHandlerConfig
from sentry.sensors.acoustic_sensor import AcousticSensor, AcousticSensorConfig
from sentry.sensors.rf_sensor import RfBandConfig, RfSensor, RfSensorConfig
from sentry.simulation.synthetic import SimulatedSensorArray, scenario_from_name
from sentry.types import SensorChannels, SensorEvent

LOG = logging.getLogger("SENTRY")


@dataclass
class DutyCycleConfig:
    active_window_s: float = 4.0
    sleep_window_s: float = 6.0
    target_active_watts: float = 2.5


@dataclass
class LiveArrayConfig:
    fallback_scenario: str = "benign"
    rng_seed: int = 42
    duty: DutyCycleConfig | None = None


def _build_rf_config(hw: dict[str, Any]) -> RfSensorConfig:
    rf = hw.get("rf_sensor", hw.get("rf_rtl", {}))
    bands_raw = rf.get("bands")
    bands = None
    if bands_raw:
        bands = [RfBandConfig(**b) for b in bands_raw]
    return RfSensorConfig(
        device_index=int(rf.get("device_index", 0)),
        integration_s=int(rf.get("integration_s", 2)),
        timeout_s=float(rf.get("timeout_s", 12.0)),
        jamming_delta_db=float(rf.get("jamming_delta_db", 12.0)),
        bands=bands or RfSensorConfig().bands,
    )


class LiveSensorArray:
    """Pi Zero 2 W sensor fusion ingest with duty-cycled heavy sensors."""

    def __init__(
        self,
        node_id: str,
        node_config: dict[str, Any],
        array_config: LiveArrayConfig | None = None,
    ) -> None:
        self.node_id = node_id
        self.node_config = node_config
        self.array_config = array_config or LiveArrayConfig()
        hw = node_config.get("hardware", {})

        self.pir = PirAdapter(PirConfig(**hw.get("pir", {})))
        self.acoustic = AcousticSensor(AcousticSensorConfig(**hw.get("acoustic", {})))
        self.rf = RfSensor(_build_rf_config(hw))
        self.visual = VisualAdapter(VisualConfig(**hw.get("visual", {})))
        self.tamper = TamperAdapter(TamperConfig(**hw.get("tamper", {})))

        mesh_cfg = hw.get("meshtastic", {})
        mesh_local = {k: v for k, v in mesh_cfg.items() if k not in ("peers", "fallback_spool")}
        self.mesh = MeshtasticHandler(
            MeshtasticHandlerConfig(
                local=MeshNodeConfig(node_id=node_id, **mesh_local),
                peers=list(mesh_cfg.get("peers", ["sentry-pi-zero-002"])),
            )
        )

        sim_cfg = node_config.get("simulation", {})
        scenario = str(sim_cfg.get("fallback_scenario", self.array_config.fallback_scenario))
        self._sim = SimulatedSensorArray(
            node_id,
            scenario_from_name(scenario),
            rng_seed=int(sim_cfg.get("rng_seed", self.array_config.rng_seed)),
        )
        self._seq = 0
        self._cycle_start = time.monotonic()
        duty_cfg = hw.get("duty_cycle", {})
        if self.array_config.duty is not None:
            self.duty = self.array_config.duty
        elif duty_cfg:
            self.duty = DutyCycleConfig(**duty_cfg)
        else:
            self.duty = DutyCycleConfig()

    @property
    def relay(self) -> MeshtasticHandler:
        return self.mesh

    def _in_active_window(self, now: float) -> bool:
        period = self.duty.active_window_s + self.duty.sleep_window_s
        if period <= 0:
            return True
        phase = (now - self._cycle_start) % period
        return phase < self.duty.active_window_s

    def sample(self, timestamp_s: float | None = None) -> SensorEvent:
        ts = time.time() if timestamp_s is None else timestamp_s
        active = self._in_active_window(time.monotonic())
        sim = self._sim.sample(ts)

        pir = float(self.pir.read()) if self.pir.available else sim.channels.pir

        if active and self.acoustic.available:
            ac = self.acoustic.read()
            acoustic = ac.score
            propeller_peak = ac.propeller_peak
        else:
            acoustic = sim.channels.acoustic
            propeller_peak = sim.flags.get("acoustic_propeller_peak", False)

        if active and self.rf.available:
            rf_result = self.rf.read(synthetic_rf=sim.channels.rf, synthetic_jamming=sim.flags.get("jamming_suspected", False))
        else:
            rf_result = self.rf.read(synthetic_rf=sim.channels.rf, synthetic_jamming=sim.flags.get("jamming_suspected", False))

        visual = float(self.visual.read()) if (active and self.visual.available) else sim.channels.visual
        tampered = self.tamper.read() if self.tamper.available else False

        flags = {
            "jamming_suspected": rf_result.jamming,
            "low_visibility": sim.flags.get("low_visibility", False),
            "tamper_detected": tampered,
            "hardware_active_window": active,
            "rf_burst_2g4": rf_result.burst_2g4,
            "rf_burst_5g8": rf_result.burst_5g8,
            "acoustic_propeller_peak": propeller_peak,
            "rf_source": rf_result.source,
            "fallback_channels": self.fallback_report(),
        }

        event = SensorEvent(
            node_id=self.node_id,
            seq=self._seq,
            timestamp_s=ts,
            channels=SensorChannels(pir=pir, acoustic=acoustic, rf=rf_result.score, visual=visual),
            flags=flags,
        )
        self._seq += 1
        return event

    def fallback_report(self) -> dict[str, bool]:
        return {
            "pir": not self.pir.available,
            "acoustic": not self.acoustic.available,
            "rf": not self.rf.available,
            "visual": not self.visual.available,
            "tamper": not self.tamper.available,
            "meshtastic": not self.mesh.available,
        }

    def stream(self, duration_s: float, rate_hz: float) -> Iterator[SensorEvent]:
        dt = 1.0 / rate_hz
        t0 = time.time()
        elapsed = 0.0
        while elapsed <= duration_s:
            yield self.sample(t0 + elapsed)
            time.sleep(dt)
            elapsed += dt

    def close(self) -> None:
        self.pir.close()
        self.acoustic.close()
        self.visual.close()
        self.tamper.close()
        self.mesh.close()
