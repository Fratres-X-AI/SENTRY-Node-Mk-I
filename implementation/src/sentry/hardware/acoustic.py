"""Acoustic FFT adapter — 100–500 Hz peak energy (PyAudio + NumPy)."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from sentry.hardware import adapter_status, clamp01

LOG = logging.getLogger("SENTRY")


@dataclass
class AcousticConfig:
    sample_rate_hz: int = 16_000
    frame_samples: int = 4096
    band_low_hz: float = 100.0
    band_high_hz: float = 500.0
    device_index: int | None = None
    peak_ratio_threshold: float = 0.35


def band_peak_ratio(samples: list[float], sample_rate_hz: int, low_hz: float, high_hz: float) -> float:
    """Ratio of in-band FFT energy to total energy (pure Python fallback)."""
    n = len(samples)
    if n < 8:
        return 0.0
    try:
        import numpy as np

        arr = np.asarray(samples, dtype=np.float64)
        spectrum = np.abs(np.fft.rfft(arr)) ** 2
        freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate_hz)
        total = float(spectrum.sum()) + 1e-12
        mask = (freqs >= low_hz) & (freqs <= high_hz)
        band = float(spectrum[mask].sum())
        return clamp01(band / total)
    except ImportError:
        # Coarse Goertzel-style energy estimate without numpy
        band_energy = 0.0
        total_energy = 0.0
        for i, x in enumerate(samples):
            total_energy += x * x
            phase = 2.0 * math.pi * 250.0 * i / sample_rate_hz
            band_energy += x * math.sin(phase)
        if total_energy <= 1e-12:
            return 0.0
        return clamp01(abs(band_energy) / (math.sqrt(total_energy) * n + 1e-12))


def probe(config: AcousticConfig | None = None) -> dict[str, Any]:
    cfg = config or AcousticConfig()
    try:
        import pyaudio  # noqa: F401
    except ImportError:
        return adapter_status("acoustic", False, "pyaudio not installed")
    try:
        import numpy as np  # noqa: F401
    except ImportError:
        return adapter_status("acoustic", False, "numpy not installed (pip install sentry[hardware])")
    pa = __import__("pyaudio").PyAudio()
    try:
        stream = pa.open(
            format=pa.get_format_from_width(2),
            channels=1,
            rate=cfg.sample_rate_hz,
            input=True,
            frames_per_buffer=cfg.frame_samples,
            input_device_index=cfg.device_index,
        )
        raw = stream.read(cfg.frame_samples, exception_on_overflow=False)
        stream.stop_stream()
        stream.close()
    except Exception as exc:  # noqa: BLE001 — hardware probe must not crash
        pa.terminate()
        return adapter_status("acoustic", False, str(exc)[:200])
    pa.terminate()
    import numpy as np

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    ratio = band_peak_ratio(samples.tolist(), cfg.sample_rate_hz, cfg.band_low_hz, cfg.band_high_hz)
    return adapter_status("acoustic", True, f"band_ratio={ratio:.3f}")


class AcousticAdapter:
    """Passive acoustic channel using 100–500 Hz FFT peak ratio."""

    def __init__(self, config: AcousticConfig | None = None) -> None:
        self.config = config or AcousticConfig()
        self._pa = None
        self._available = False
        try:
            import pyaudio
            import numpy  # noqa: F401

            self._pa = pyaudio.PyAudio()
            self._available = True
        except ImportError:
            LOG.info("SENTRY acoustic adapter unavailable — install sentry[hardware]")

    @property
    def available(self) -> bool:
        return self._available and self._pa is not None

    def close(self) -> None:
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None

    def read(self) -> float:
        if not self.available or self._pa is None:
            return 0.0
        import numpy as np

        pa = self._pa
        try:
            stream = pa.open(
                format=pa.get_format_from_width(2),
                channels=1,
                rate=self.config.sample_rate_hz,
                input=True,
                frames_per_buffer=self.config.frame_samples,
                input_device_index=self.config.device_index,
            )
            raw = stream.read(self.config.frame_samples, exception_on_overflow=False)
            stream.stop_stream()
            stream.close()
        except Exception as exc:  # noqa: BLE001
            LOG.warning("SENTRY acoustic read failed: %s", exc)
            return 0.0
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
        return band_peak_ratio(
            samples.tolist(),
            self.config.sample_rate_hz,
            self.config.band_low_hz,
            self.config.band_high_hz,
        )
