"""Power and thermal telemetry for Pi Zero 2 W duty-cycle budgeting."""

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
class PowerSample:
    timestamp_s: float
    estimated_watts: float
    cpu_temp_c: float | None
    throttled: bool
    source: str
    duty_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "power_sample.v1",
            "codename": "SENTRY",
            "timestamp_s": self.timestamp_s,
            "estimated_watts": round(self.estimated_watts, 3),
            "cpu_temp_c": self.cpu_temp_c,
            "throttled": self.throttled,
            "source": self.source,
            "duty_active": self.duty_active,
        }


@dataclass
class PowerBudget:
    idle_watts: float = 1.2
    active_watts: float = 2.8
    rtl_sweep_watts: float = 0.6
    acoustic_watts: float = 0.3
    visual_watts: float = 0.4


@dataclass
class PowerLogger:
    budget: PowerBudget = field(default_factory=PowerBudget)
    log_path: Path | None = None
    _samples: list[PowerSample] = field(default_factory=list)

    def _read_pi_telemetry(self) -> tuple[float | None, bool]:
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

    def estimate(
        self,
        duty_active: bool,
        rtl_active: bool = False,
        acoustic_active: bool = False,
        visual_active: bool = False,
    ) -> PowerSample:
        ts = time.time()
        if is_raspberry_pi():
            temp_c, throttled = self._read_pi_telemetry()
            watts = self.budget.idle_watts
            if duty_active:
                watts = self.budget.active_watts
            if rtl_active:
                watts += self.budget.rtl_sweep_watts
            if acoustic_active:
                watts += self.budget.acoustic_watts
            if visual_active:
                watts += self.budget.visual_watts
            sample = PowerSample(
                timestamp_s=ts,
                estimated_watts=watts,
                cpu_temp_c=temp_c,
                throttled=throttled,
                source="pi_telemetry",
                duty_active=duty_active,
            )
        else:
            sample = PowerSample(
                timestamp_s=ts,
                estimated_watts=self.budget.active_watts if duty_active else self.budget.idle_watts,
                cpu_temp_c=45.0 if duty_active else 38.0,
                throttled=False,
                source="desktop_simulation",
                duty_active=duty_active,
            )
        self._samples.append(sample)
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(sample.to_dict()) + "\n")
        return sample

    def summary(self) -> dict[str, Any]:
        if not self._samples:
            return {"samples": 0}
        watts = [s.estimated_watts for s in self._samples]
        temps = [s.cpu_temp_c for s in self._samples if s.cpu_temp_c is not None]
        return {
            "samples": len(self._samples),
            "mean_watts": round(sum(watts) / len(watts), 3),
            "max_watts": round(max(watts), 3),
            "mean_temp_c": round(sum(temps) / len(temps), 2) if temps else None,
            "any_throttled": any(s.throttled for s in self._samples),
        }
