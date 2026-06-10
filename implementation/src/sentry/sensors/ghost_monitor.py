"""Passive network anomaly monitor using psutil counters only."""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover - optional on stripped builds
    psutil = None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / (len(values) - 1))


@dataclass
class GhostMonitorConfig:
    enabled: bool = True
    interface: str | None = None
    sample_interval_s: float = 30.0
    window: int = 12
    min_delta_bytes: float = 512.0
    regularity_cv_threshold: float = 0.60
    anomaly_score: float = 0.20


@dataclass
class GhostMonitorResult:
    score: float
    suspicious: bool
    detail: str

    def flags(self) -> dict[str, Any]:
        return {
            "passive_network_anomaly": self.suspicious,
            "ghost_monitor_score": self.score,
            "ghost_monitor_detail": self.detail,
        }


@dataclass
class GhostMonitor:
    """Detect regular small network bursts without packet capture or payload access."""

    config: GhostMonitorConfig = field(default_factory=GhostMonitorConfig)
    _history: deque[tuple[float, float]] = field(init=False, repr=False)
    _last_sample_s: float = field(default=0.0, init=False)
    _last_result: GhostMonitorResult = field(default_factory=lambda: GhostMonitorResult(0.0, False, "not sampled"), init=False)

    def __post_init__(self) -> None:
        self._history = deque(maxlen=max(4, self.config.window))

    @property
    def available(self) -> bool:
        return psutil is not None and self.config.enabled

    def _bytes_sent(self) -> float:
        if psutil is None:
            return 0.0
        counters = psutil.net_io_counters(pernic=bool(self.config.interface))
        if self.config.interface:
            stats = counters.get(self.config.interface)
            if stats is None:
                return 0.0
            return float(stats.bytes_sent + stats.bytes_recv)
        return float(counters.bytes_sent + counters.bytes_recv)

    def sample(self, now_s: float | None = None, force: bool = False) -> GhostMonitorResult:
        now = time.monotonic() if now_s is None else now_s
        if not self.available:
            self._last_result = GhostMonitorResult(0.0, False, "psutil unavailable")
            return self._last_result
        if not force and now - self._last_sample_s < self.config.sample_interval_s:
            return self._last_result

        self._last_sample_s = now
        self._history.append((now, self._bytes_sent()))
        if len(self._history) < 4:
            self._last_result = GhostMonitorResult(0.0, False, "warming baseline")
            return self._last_result

        times = [row[0] for row in self._history]
        deltas = [abs(self._history[i][1] - self._history[i - 1][1]) for i in range(1, len(self._history))]
        intervals_ms = [(times[i] - times[i - 1]) * 1000.0 for i in range(1, len(times))]
        mean_delta = _mean(deltas)
        interval_mean = _mean(intervals_ms)
        cv = _stddev(intervals_ms) / interval_mean if interval_mean > 0 else 0.0

        suspicious = mean_delta >= self.config.min_delta_bytes and cv <= self.config.regularity_cv_threshold
        score = self.config.anomaly_score if suspicious else 0.0
        detail = f"mean_delta={mean_delta:.1f}B interval_ms={interval_mean:.1f} cv={cv:.3f}"
        self._last_result = GhostMonitorResult(score, suspicious, detail)
        return self._last_result
