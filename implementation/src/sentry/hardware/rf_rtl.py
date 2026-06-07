"""RTL-SDR rtl_power sweep adapter."""

from __future__ import annotations

import csv
import io
import logging
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from sentry.hardware import adapter_status, clamp01
from sentry.hardware.rf_friis import rtl_power_anomaly_score

LOG = logging.getLogger("SENTRY")


@dataclass
class RtlConfig:
    device_index: int = 0
    start_mhz: float = 433.0
    end_mhz: float = 434.0
    bin_hz: int = 10_000
    integration_s: int = 1
    timeout_s: float = 8.0
    jamming_delta_db: float = 12.0


def parse_rtl_power_csv(text: str) -> list[float]:
    """Parse rtl_power CSV rows; return all power values in dBm."""
    values: list[float] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        if len(parts) < 7:
            continue
        try:
            low_hz = float(parts[2])
            high_hz = float(parts[3])
            step_hz = float(parts[4])
            dbm_values = [float(x) for x in parts[6:]]
        except ValueError:
            continue
        for i, dbm in enumerate(dbm_values):
            freq = low_hz + i * step_hz
            if low_hz <= freq <= high_hz:
                values.append(dbm)
    return values


def probe(config: RtlConfig | None = None) -> dict[str, Any]:
    cfg = config or RtlConfig()
    exe = shutil.which("rtl_power")
    if exe is None:
        return adapter_status("rf_rtl", False, "rtl_power not in PATH")
    try:
        proc = subprocess.run(
            [
                exe,
                "-d",
                str(cfg.device_index),
                "-f",
                f"{cfg.start_mhz}M:{cfg.end_mhz}M:{cfg.bin_hz}",
                "-i",
                str(cfg.integration_s),
                "-1",
            ],
            capture_output=True,
            text=True,
            timeout=cfg.timeout_s,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return adapter_status("rf_rtl", False, f"rtl_power failed: {exc}")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "rtl_power error").strip()[:200]
        return adapter_status("rf_rtl", False, detail)
    values = parse_rtl_power_csv(proc.stdout)
    if not values:
        return adapter_status("rf_rtl", False, "rtl_power returned no bins")
    return adapter_status("rf_rtl", True, f"bins={len(values)} peak={max(values):.1f}dBm")


class RtlPowerAdapter:
    """Passive RF anomaly channel via rtl_power."""

    def __init__(self, config: RtlConfig | None = None) -> None:
        self.config = config or RtlConfig()
        self._baseline: float | None = None
        self._available = shutil.which("rtl_power") is not None

    @property
    def available(self) -> bool:
        return self._available

    def read(self) -> tuple[float, bool]:
        if not self._available:
            return 0.0, False
        exe = shutil.which("rtl_power")
        assert exe is not None
        try:
            proc = subprocess.run(
                [
                    exe,
                    "-d",
                    str(self.config.device_index),
                    "-f",
                    f"{self.config.start_mhz}M:{self.config.end_mhz}M:{self.config.bin_hz}",
                    "-i",
                    str(self.config.integration_s),
                    "-1",
                ],
                capture_output=True,
                text=True,
                timeout=self.config.timeout_s,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            LOG.warning("SENTRY rf_rtl read failed: %s", exc)
            return 0.0, False
        if proc.returncode != 0:
            LOG.warning("SENTRY rf_rtl nonzero exit: %s", proc.stderr.strip()[:120])
            return 0.0, False
        values = parse_rtl_power_csv(proc.stdout)
        if not values:
            return 0.0, False
        if self._baseline is None:
            self._baseline = min(values)
        score, jamming = rtl_power_anomaly_score(
            values,
            baseline_dbm=self._baseline,
            jamming_delta_db=self.config.jamming_delta_db,
        )
        return clamp01(score), jamming
