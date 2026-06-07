"""GPU batch FFT for 10k+ synthetic acoustic streams (RunPod dev only)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from sentry.gpu.device import require_cuda


@dataclass
class GpuFftResult:
    batch_size: int
    frame_samples: int
    mean_band_energy: float
    propeller_hits: int
    device: str
    elapsed_s: float


def gpu_batch_fft_propeller(
    batch_size: int | None = None,
    frame_samples: int = 4096,
    sample_rate_hz: int = 16_000,
    band_low_hz: float = 100.0,
    band_high_hz: float = 500.0,
    propeller_frac: float = 0.35,
) -> GpuFftResult:
    """
    Simulate batch_size parallel MEMS streams; FFT entirely on GPU.
    BLUNT: Irrelevant for Pi Zero 2 W field — CPU + PyAudio there.
    """
    import time

    import torch

    device = require_cuda()
    batch_size = batch_size or int(os.environ.get("SENTRY_GPU_FFT_BATCH", 16384))

    t0 = time.perf_counter()
    # [B, T] synthetic waveforms
    t = torch.arange(frame_samples, device=device, dtype=torch.float32)
    freqs = torch.where(
        torch.rand(batch_size, device=device) < propeller_frac,
        torch.empty(batch_size, device=device).uniform_(120, 480),
        torch.empty(batch_size, device=device).uniform_(600, 3000),
    )
    phase = 2 * 3.14159265 * freqs.unsqueeze(1) * t.unsqueeze(0) / sample_rate_hz
    signals = torch.sin(phase) + 0.05 * torch.randn(batch_size, frame_samples, device=device)

    # Batched FFT
    spectrum = torch.abs(torch.fft.rfft(signals, dim=1))
    fft_freqs = torch.fft.rfftfreq(frame_samples, d=1.0 / sample_rate_hz).to(device)
    mask = (fft_freqs >= band_low_hz) & (fft_freqs <= band_high_hz)
    band = spectrum[:, mask]
    total = spectrum.sum(dim=1) + 1e-9
    band_ratio = band.sum(dim=1) / total
    propeller_hits = int((band_ratio > 0.25).sum().item())
    elapsed = time.perf_counter() - t0

    # Keep tensors live through extra matmul to ensure GPU work
    _ = torch.mm(signals[: min(512, batch_size)], signals[: min(512, batch_size)].T)

    return GpuFftResult(
        batch_size=batch_size,
        frame_samples=frame_samples,
        mean_band_energy=float(band_ratio.mean().item()),
        propeller_hits=propeller_hits,
        device=str(device),
        elapsed_s=round(elapsed, 4),
    )
