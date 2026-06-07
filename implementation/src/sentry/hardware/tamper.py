"""GPIO tamper / enclosure switch adapter."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sentry.hardware import adapter_status, is_raspberry_pi
from sentry.hardware.pir import _GpioBackend

LOG = logging.getLogger("SENTRY")


@dataclass
class TamperConfig:
    gpio_pin: int = 27
    pull: str = "up"
    active_low: bool = True


def probe(config: TamperConfig | None = None) -> dict[str, Any]:
    cfg = config or TamperConfig()
    if not is_raspberry_pi():
        return adapter_status("tamper_gpio", False, "not running on Raspberry Pi")
    backend = _GpioBackend(cfg.gpio_pin, cfg.pull)
    level = backend.read_level()
    mode = backend._mode
    backend.close()
    if mode == "mock":
        return adapter_status("tamper_gpio", False, "lgpio/RPi.GPIO unavailable")
    tampered = (level == 0) if cfg.active_low else (level == 1)
    return adapter_status("tamper_gpio", True, f"mode={mode} tampered={tampered}")


class TamperAdapter:
    """Enclosure tamper switch — sets audit/tamper flags when triggered."""

    def __init__(self, config: TamperConfig | None = None) -> None:
        self.config = config or TamperConfig()
        self._backend: _GpioBackend | None = None
        if is_raspberry_pi():
            self._backend = _GpioBackend(self.config.gpio_pin, self.config.pull)
            if self._backend._mode == "mock":
                self._backend = None

    @property
    def available(self) -> bool:
        return self._backend is not None

    def close(self) -> None:
        if self._backend is not None:
            self._backend.close()
            self._backend = None

    def read(self) -> bool:
        if self._backend is None:
            return False
        level = self._backend.read_level()
        if self.config.active_low:
            return level == 0
        return level == 1
