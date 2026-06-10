#!/usr/bin/env python3
"""Blast synthetic RF/acoustic events through the guardian in-process."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "implementation" / "src"))

from sentry.guardian import SentryGuardian  # noqa: E402
from sentry.types import SensorChannels, SensorEvent  # noqa: E402

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]


def main() -> int:
    guardian = SentryGuardian("sentry-flood-test", {})
    process = psutil.Process() if psutil is not None else None
    rss_start = process.memory_info().rss if process is not None else 0
    start = time.time()
    count = 0
    duration_s = 5.0
    while time.time() - start < duration_s:
        event = SensorEvent(
            node_id="sentry-flood-test",
            seq=count,
            timestamp_s=time.time(),
            channels=SensorChannels(pir=0.1, acoustic=0.9, rf=0.95, visual=0.1),
            flags={"rf_burst_2g4": True, "acoustic_propeller_peak": True, "passive_score": 0.0},
        )
        guardian.process(event)
        count += 1
    rss_end = process.memory_info().rss if process is not None else 0
    report = {
        "events": count,
        "events_per_second": count / duration_s,
        "rss_delta_mb": round((rss_end - rss_start) / (1024 * 1024), 3),
        "pass": process is None or (rss_end - rss_start) < 50 * 1024 * 1024,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
