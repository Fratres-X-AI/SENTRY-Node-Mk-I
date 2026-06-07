from __future__ import annotations

import math

from sentry.hardware.acoustic import band_peak_ratio


def test_band_peak_ratio_detects_tone() -> None:
    sr = 8000
    freq = 250.0
    samples = [math.sin(2 * math.pi * freq * i / sr) for i in range(4096)]
    ratio = band_peak_ratio(samples, sr, 100.0, 500.0)
    assert ratio > 0.5


def test_band_peak_ratio_silence_low() -> None:
    samples = [0.0] * 512
    ratio = band_peak_ratio(samples, 8000, 100.0, 500.0)
    assert ratio == 0.0
