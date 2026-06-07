"""GPIO PIR motion adapter (lgpio / RPi.GPIO with simulation fallback)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from sentry.hardware import adapter_status, clamp01, is_raspberry_pi

LOG = logging.getLogger("SENTRY")


@dataclass
class PirConfig:
    gpio_pin: int = 17
    pull: str = "down"
    debounce_s: float = 0.2


class _GpioBackend:
    def __init__(self, pin: int, pull: str) -> None:
        self.pin = pin
        self._chip = None
        self._mode = "mock"
        try:
            import lgpio

            chip = lgpio.gpiochip_open(0)
            flags = lgpio.SET_PULL_DOWN if pull == "down" else lgpio.SET_PULL_UP
            lgpio.gpio_claim_input(chip, pin, flags)
            self._chip = chip
            self._mode = "lgpio"
            return
        except Exception:
            pass
        try:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            pud = GPIO.PUD_DOWN if pull == "down" else GPIO.PUD_UP
            GPIO.setup(pin, GPIO.IN, pull_up_down=pud)
            self._mode = "RPi.GPIO"
            self._gpio = GPIO
        except Exception:
            self._mode = "mock"

    def read_level(self) -> int:
        if self._mode == "lgpio" and self._chip is not None:
            import lgpio

            return int(lgpio.gpio_read(self._chip, self.pin))
        if self._mode == "RPi.GPIO":
            return int(self._gpio.input(self.pin))
        return 0

    def close(self) -> None:
        if self._mode == "lgpio" and self._chip is not None:
            import lgpio

            lgpio.gpiochip_close(self._chip)
            self._chip = None
        elif self._mode == "RPi.GPIO":
            self._gpio.cleanup(self.pin)


def probe(config: PirConfig | None = None) -> dict[str, Any]:
    cfg = config or PirConfig()
    if not is_raspberry_pi():
        return adapter_status("pir_gpio", False, "not running on Raspberry Pi")
    backend = _GpioBackend(cfg.gpio_pin, cfg.pull)
    level = backend.read_level()
    mode = backend._mode
    backend.close()
    if mode == "mock":
        return adapter_status("pir_gpio", False, "lgpio/RPi.GPIO unavailable")
    return adapter_status("pir_gpio", True, f"mode={mode} level={level}")


class PirAdapter:
    """PIR motion normalized to 0–1."""

    def __init__(self, config: PirConfig | None = None) -> None:
        self.config = config or PirConfig()
        self._backend: _GpioBackend | None = None
        self._last_high = 0.0
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

    def read(self) -> float:
        if self._backend is None:
            return 0.0
        level = self._backend.read_level()
        now = time.monotonic()
        if level:
            self._last_high = now
        recent = (now - self._last_high) < 2.0
        return 1.0 if level or recent else 0.0
