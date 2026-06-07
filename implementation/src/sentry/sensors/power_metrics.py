"""CPU/RAM telemetry and datasheet-based current draw estimation."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sentry.hardware import is_raspberry_pi

LOG = logging.getLogger("SENTRY")


@dataclass
class PowerMetricsConfig:
    log_path: Path | None = None
    target_avg_watts: float = 5.0
    pi_zero_idle_w: float = 1.0
    pi_zero_active_w: float = 2.5
    rtl_sweep_w: float = 0.55
    acoustic_w: float = 0.25
    lora_tx_w: float = 0.35
    duty_active_fraction: float = 0.4


@dataclass
class PowerSample:
    timestamp_s: float
    cpu_percent: float
    ram_used_mb: float
    ram_total_mb: float
    estimated_watts: float
    duty_active: bool
    throttled: bool
    cpu_temp_c: float | None
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "power_metrics.v1",
            "codename": "SENTRY",
            "timestamp_s": self.timestamp_s,
            "cpu_percent": round(self.cpu_percent, 1),
            "ram_used_mb": round(self.ram_used_mb, 1),
            "ram_total_mb": round(self.ram_total_mb, 1),
            "estimated_watts": round(self.estimated_watts, 3),
            "duty_active": self.duty_active,
            "throttled": self.throttled,
            "cpu_temp_c": self.cpu_temp_c,
            "source": self.source,
        }


class PowerMetrics:
    """Tracks resource use and estimates draw for Zero 2 W duty-cycle budgeting."""

    def __init__(self, config: PowerMetricsConfig | None = None) -> None:
        self.config = config or PowerMetricsConfig()
        self._samples: list[PowerSample] = []
        self._duty_active_count = 0
        self._duty_sleep_count = 0
        self._psutil = None
        try:
            import psutil

            self._psutil = psutil
        except ImportError:
            LOG.info("SENTRY power_metrics: psutil not installed — using estimates only")

    def _pi_telemetry(self) -> tuple[float | None, bool]:
        temp_c: float | None = None
        throttled = False
        try:
            out = subprocess.check_output(["vcgencmd", "measure_temp"], text=True, timeout=2)
            m = re.search(r"temp=([\d.]+)'C", out)
            if m:
                temp_c = float(m.group(1))
        except (subprocess.SubprocessError, FileNotFoundError, ValueError):
            pass
        try:
            out = subprocess.check_output(["vcgencmd", "get_throttled"], text=True, timeout=2)
            throttled = "0x0" not in out.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return temp_c, throttled

    def record(
        self,
        duty_active: bool,
        rtl_active: bool = False,
        acoustic_active: bool = False,
        lora_tx: bool = False,
    ) -> PowerSample:
        ts = time.time()
        cpu_pct = 0.0
        ram_used = 256.0
        ram_total = 512.0

        if self._psutil is not None:
            cpu_pct = float(self._psutil.cpu_percent(interval=None))
            mem = self._psutil.virtual_memory()
            ram_used = mem.used / (1024 * 1024)
            ram_total = mem.total / (1024 * 1024)

        cfg = self.config
        watts = cfg.pi_zero_idle_w if not duty_active else cfg.pi_zero_active_w
        if rtl_active:
            watts += cfg.rtl_sweep_w
        if acoustic_active:
            watts += cfg.acoustic_w
        if lora_tx:
            watts += cfg.lora_tx_w

        if duty_active:
            self._duty_active_count += 1
        else:
            self._duty_sleep_count += 1

        if is_raspberry_pi():
            temp_c, throttled = self._pi_telemetry()
            source = "pi_psutil" if self._psutil else "pi_estimate"
        else:
            temp_c = 45.0 if duty_active else 38.0
            throttled = cpu_pct > 90.0
            source = "desktop_simulation"

        sample = PowerSample(
            timestamp_s=ts,
            cpu_percent=cpu_pct,
            ram_used_mb=ram_used,
            ram_total_mb=ram_total,
            estimated_watts=watts,
            duty_active=duty_active,
            throttled=throttled,
            cpu_temp_c=temp_c,
            source=source,
        )
        self._samples.append(sample)

        if self.config.log_path:
            self.config.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(sample.to_dict()) + "\n")

        return sample

    def summary(self) -> dict[str, Any]:
        if not self._samples:
            return {"samples": 0}
        watts = [s.estimated_watts for s in self._samples]
        cpus = [s.cpu_percent for s in self._samples]
        total_duty = self._duty_active_count + self._duty_sleep_count
        active_frac = self._duty_active_count / total_duty if total_duty else 0.0
        mean_w = sum(watts) / len(watts)
        return {
            "samples": len(self._samples),
            "mean_watts": round(mean_w, 3),
            "max_watts": round(max(watts), 3),
            "mean_cpu_percent": round(sum(cpus) / len(cpus), 1),
            "duty_active_fraction": round(active_frac, 3),
            "target_avg_watts": self.config.target_avg_watts,
            "under_target": mean_w <= self.config.target_avg_watts,
            "any_throttled": any(s.throttled for s in self._samples),
        }
