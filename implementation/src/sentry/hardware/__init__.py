"""Hardware adapter utilities for SENTRY Pi Zero 2 W deployment."""

from __future__ import annotations

import platform
import sys
from typing import Any


def is_raspberry_pi() -> bool:
    if sys.platform != "linux":
        return False
    try:
        model = open("/proc/device-tree/model", "rb").read().decode("utf-8", errors="ignore")
    except OSError:
        return False
    return "Raspberry Pi" in model


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def adapter_status(name: str, available: bool, detail: str = "") -> dict[str, Any]:
    return {
        "adapter": name,
        "available": available,
        "detail": detail,
        "platform": platform.platform(),
        "pi_detected": is_raspberry_pi(),
    }
