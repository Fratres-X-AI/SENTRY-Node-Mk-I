"""Acoustic propeller-band detection — PyAudio + SciPy FFT peak find (100–500 Hz)."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from sentry.hardware import adapter_status, clamp01

LOG = logging.getLogger("SENTRY")


@dataclass
class AcousticSensorConfig:
    sample_rate_hz: int = 16_000
    frame_samples: int = 4096
    band_low_hz: float = 100.0
    band_high_hz: float = 500.0
    device_index: int | None = None
    peak_prominence: float = 0.08
    wind_reject_ratio: float = 0.92


@dataclass
class AcousticReadResult:
    score: float
    propeller_peak: bool
    peak_freq_hz: float | None
    peak_count: int
    source: str


def _fft_peaks(samples: list[float], sample_rate_hz: int, cfg: AcousticSensorConfig) -> AcousticReadResult:
    try:
        import numpy as np
        from scipy.signal import find_peaks
    except ImportError:
        # numpy-only fallback
        import numpy as np

        arr = np.asarray(samples, dtype=np.float64)
        spectrum = np.abs(np.fft.rfft(arr))
        freqs = np.fft.rfftfreq(len(arr), d=1.0 / sample_rate_hz)
        mask = (freqs >= cfg.band_low_hz) & (freqs <= cfg.band_high_hz)
        if not mask.any():
            return AcousticReadResult(0.0, False, None, 0, "numpy_fallback")
        band_spec = spectrum[mask]
        band_freqs = freqs[mask]
        peak_idx = int(np.argmax(band_spec))
        fallback_peak_freq = float(band_freqs[peak_idx])
        total = float(spectrum.sum()) + 1e-12
        score = clamp01(float(band_spec[peak_idx]) / total * 4.0)
        return AcousticReadResult(
            score,
            100.0 <= fallback_peak_freq <= 500.0 and score > 0.25,
            fallback_peak_freq,
            1,
            "numpy_fallback",
        )

    arr = np.asarray(samples, dtype=np.float64)
    window = np.hanning(len(arr))
    spectrum = np.abs(np.fft.rfft(arr * window))
    freqs = np.fft.rfftfreq(len(arr), d=1.0 / sample_rate_hz)
    mask = (freqs >= cfg.band_low_hz) & (freqs <= cfg.band_high_hz)
    band_spec = spectrum[mask]
    band_freqs = freqs[mask]
    if len(band_spec) == 0:
        return AcousticReadResult(0.0, False, None, 0, "scipy")

    norm = band_spec / (band_spec.max() + 1e-12)
    peaks, props = find_peaks(norm, prominence=cfg.peak_prominence)
    total_energy = float(spectrum.sum()) + 1e-12
    band_energy = float(band_spec.sum())
    score = clamp01(band_energy / total_energy * 2.5)

    # Wind: broadband lift without narrow peaks
    if score > 0.4 and len(peaks) == 0:
        score *= cfg.wind_reject_ratio

    peak_freq: float | None = float(band_freqs[int(peaks[0])]) if len(peaks) else None
    propeller = peak_freq is not None and 100.0 <= peak_freq <= 500.0 and len(peaks) <= 4

    return AcousticReadResult(score, propeller, peak_freq, len(peaks), "scipy")


def generate_synthetic_tone(
    freq_hz: float, sample_rate_hz: int, n_samples: int, noise: float = 0.02
) -> list[float]:
    return [
        math.sin(2 * math.pi * freq_hz * i / sample_rate_hz) + noise * math.sin(i)
        for i in range(n_samples)
    ]


class AcousticSensor:
    """MEMS USB mic propeller-band passive acoustic channel."""

    def __init__(self, config: AcousticSensorConfig | None = None) -> None:
        self.config = config or AcousticSensorConfig()
        self._pa = None
        self._available = False
        try:
            import pyaudio
            import numpy  # noqa: F401
            import scipy  # noqa: F401

            self._pa = pyaudio.PyAudio()
            self._available = True
        except ImportError:
            LOG.info("SENTRY acoustic_sensor: install sentry[hardware] for PyAudio+SciPy")

    @property
    def available(self) -> bool:
        return self._available and self._pa is not None

    def probe(self) -> dict[str, Any]:
        if not self.available:
            return adapter_status("acoustic_sensor", False, "pyaudio/scipy/numpy not available")
        try:
            result = self.read()
            return adapter_status(
                "acoustic_sensor",
                True,
                f"score={result.score:.3f} peaks={result.peak_count} source={result.source}",
            )
        except Exception as exc:  # noqa: BLE001
            return adapter_status("acoustic_sensor", False, str(exc)[:200])

    def close(self) -> None:
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None

    def read(self, synthetic_score: float = 0.0) -> AcousticReadResult:
        if not self.available or self._pa is None:
            return AcousticReadResult(
                clamp01(synthetic_score),
                synthetic_score > 0.35,
                220.0 if synthetic_score > 0.35 else None,
                1 if synthetic_score > 0.35 else 0,
                "synthetic",
            )

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
            LOG.warning("SENTRY acoustic_sensor read failed: %s", exc)
            return AcousticReadResult(clamp01(synthetic_score), False, None, 0, "error")

        import numpy as np

        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
        return _fft_peaks(samples.tolist(), self.config.sample_rate_hz, self.config)


def gpu_sim_batch_fft(
    batch_size: int = 16384,
    config: AcousticSensorConfig | None = None,
) -> AcousticReadResult:
    """
    RunPod dev: torch.fft on GPU for batch_size parallel synthetic streams.
    BLUNT: Not used on Pi field node (CPU-only, <5W duty cycle).
    """
    try:
        from sentry.gpu.acoustic_batch import gpu_batch_fft_propeller

        r = gpu_batch_fft_propeller(batch_size=batch_size)
        score = clamp01(r.mean_band_energy)
        return AcousticReadResult(
            score=score,
            propeller_peak=r.propeller_hits > batch_size // 4,
            peak_freq_hz=220.0,
            peak_count=r.propeller_hits,
            source=f"gpu_fft_{r.device}",
        )
    except Exception as exc:  # noqa: BLE001
        LOG.warning("SENTRY gpu_sim_batch_fft failed: %s", exc)
        return AcousticReadResult(0.0, False, None, 0, "gpu_error")
