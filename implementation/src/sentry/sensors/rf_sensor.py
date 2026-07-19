"""RTL-SDR passive EW burst detection — planned 2.4 GHz path + 5.8 GHz synthetic fallback.

GAP (documented): RTL-SDR Blog V4 still uses an RTL2832-class receiver path and cannot
receive 5.8 GHz natively. The 5g8 band uses simulation fallback until a suitable
front-end is added.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from sentry.hardware import adapter_status, clamp01
from sentry.hardware.rf_friis import friis_received_power_dbm, rtl_power_anomaly_score
from sentry.hardware.rf_rtl import parse_rtl_power_csv

LOG = logging.getLogger("SENTRY")

# RTL2832U practical upper limit (~1.766 GHz)
RTL2832_MAX_MHZ = 1766.0


@dataclass
class RfBandConfig:
    name: str
    start_mhz: float
    end_mhz: float
    bin_hz: int = 100_000
    burst_threshold_db: float = 10.0
    rtl_capable: bool = True


@dataclass
class RfSensorConfig:
    device_index: int = 0
    integration_s: int = 2
    timeout_s: float = 12.0
    jamming_delta_db: float = 12.0
    bands: list[RfBandConfig] = field(default_factory=lambda: [
        RfBandConfig("2g4", 2400.0, 2500.0, bin_hz=200_000),
        RfBandConfig("5g8", 5800.0, 5900.0, bin_hz=200_000, rtl_capable=False),
    ])


@dataclass
class RfReadResult:
    score: float
    jamming: bool
    burst_2g4: bool
    burst_5g8: bool
    band_peaks_dbm: dict[str, float]
    source: str
    detail: str = ""


def _band_rtl_capable(band: RfBandConfig) -> bool:
    if not band.rtl_capable:
        return False
    return band.end_mhz <= RTL2832_MAX_MHZ


def _run_rtl_power(cfg: RfSensorConfig, band: RfBandConfig) -> list[float]:
    exe = shutil.which("rtl_power")
    if exe is None:
        return []
    proc = subprocess.run(
        [
            exe,
            "-d",
            str(cfg.device_index),
            "-f",
            f"{band.start_mhz}M:{band.end_mhz}M:{band.bin_hz}",
            "-i",
            str(cfg.integration_s),
            "-1",
        ],
        capture_output=True,
        text=True,
        timeout=cfg.timeout_s,
    )
    if proc.returncode != 0:
        LOG.warning("SENTRY rf_sensor rtl_power exit %s: %s", proc.returncode, proc.stderr[:120])
        return []
    return parse_rtl_power_csv(proc.stdout)


class RfSensor:
    """Dual-band passive RF sensor with burst and jamming heuristics."""

    def __init__(self, config: RfSensorConfig | None = None) -> None:
        self.config = config or RfSensorConfig()
        self._baselines: dict[str, float] = {}
        self._band_index = 0
        self._rtl_available = False
        if shutil.which("rtl_power") is not None:
            probe_result = self.probe()
            self._rtl_available = probe_result.get("available", False)
        self._synthetic_5g8_peak = -55.0

    @property
    def available(self) -> bool:
        return self._rtl_available

    def probe(self) -> dict[str, Any]:
        if not self._rtl_available:
            return adapter_status("rf_sensor", False, "rtl_power not in PATH")
        band = next((b for b in self.config.bands if _band_rtl_capable(b)), None)
        if band is None:
            return adapter_status("rf_sensor", False, "no RTL-capable bands configured")
        values = _run_rtl_power(self.config, band)
        if not values:
            return adapter_status("rf_sensor", False, f"sweep failed for {band.name}")
        return adapter_status(
            "rf_sensor",
            True,
            f"band={band.name} bins={len(values)} peak={max(values):.1f}dBm",
        )

    def _synthetic_band(self, band: RfBandConfig) -> tuple[list[float], str]:
        """Fallback when hardware cannot tune band (desktop or 5.8 GHz)."""
        if band.name == "5g8":
            self._synthetic_5g8_peak += 0.1
            return [self._synthetic_5g8_peak - 5.0] * 10, "synthetic_5g8"
        return [-50.0 + (i * 0.1) for i in range(20)], "synthetic"

    def read(self, synthetic_rf: float = 0.0, synthetic_jamming: bool = False) -> RfReadResult:
        if not self.config.bands:
            return RfReadResult(0.0, False, False, False, {}, "none")

        band = self.config.bands[self._band_index % len(self.config.bands)]
        self._band_index += 1

        source = "rtl_power"
        if _band_rtl_capable(band) and self._rtl_available:
            values = _run_rtl_power(self.config, band)
        else:
            if band.name == "5g8":
                LOG.debug("SENTRY rf_sensor: 5g8 not RTL2832-capable — synthetic fallback")
            values, source = self._synthetic_band(band)
            if synthetic_rf > 0 and source.startswith("synthetic"):
                values = [v + synthetic_rf * 20.0 for v in values]

        if not values:
            return RfReadResult(
                clamp01(synthetic_rf),
                synthetic_jamming,
                False,
                False,
                {},
                "fallback",
                "empty sweep",
            )

        peak = max(values)
        if band.name not in self._baselines:
            self._baselines[band.name] = min(values)
        baseline = self._baselines[band.name]
        score, jamming = rtl_power_anomaly_score(
            values, baseline_dbm=baseline, jamming_delta_db=self.config.jamming_delta_db
        )
        burst = (peak - baseline) >= band.burst_threshold_db

        band_peaks = {band.name: peak}
        burst_2g4 = burst if band.name == "2g4" else False
        burst_5g8 = burst if band.name == "5g8" else False

        if jamming or synthetic_jamming:
            jamming = True
            score = max(score, clamp01(synthetic_rf + 0.5))

        return RfReadResult(
            score=clamp01(score),
            jamming=jamming,
            burst_2g4=burst_2g4,
            burst_5g8=burst_5g8,
            band_peaks_dbm=band_peaks,
            source=source,
        )

    def friis_note(self, distance_m: float = 500.0) -> dict[str, float]:
        """Reference Friis estimate for 2.4 GHz 10 dBm TX — planning only."""
        rx_dbm = friis_received_power_dbm(10.0, 2.0, 2.0, distance_m, 2.45e9)
        return {"distance_m": distance_m, "estimated_rx_dbm_2g4": rx_dbm}
