"""GPU melt tests — RunPod only. Pi field node has no CUDA."""

from __future__ import annotations

import pytest


@pytest.mark.gpu
def test_cuda_available(sentry_gpu: bool) -> None:
    if not sentry_gpu:
        pytest.skip("pass --gpu to run CUDA tests")
    import torch

    assert torch.cuda.is_available(), "CUDA required on RunPod melt pod"


@pytest.mark.gpu
def test_gpu_batch_fft(sentry_gpu: bool) -> None:
    if not sentry_gpu:
        pytest.skip("pass --gpu to run CUDA tests")
    from sentry.gpu.acoustic_batch import gpu_batch_fft_propeller

    r = gpu_batch_fft_propeller(batch_size=8192)
    assert r.batch_size == 8192
    assert r.propeller_hits >= 0


@pytest.mark.gpu
def test_gpu_monte_carlo(sentry_gpu: bool) -> None:
    if not sentry_gpu:
        pytest.skip("pass --gpu to run CUDA tests")
    from sentry.gpu.monte_carlo import gpu_monte_carlo_fusion

    r = gpu_monte_carlo_fusion(total=50_000, batch=16384)
    assert r.total_scenarios == 50_000
    assert sum(r.level_counts.values()) == 50_000


@pytest.mark.gpu
def test_acoustic_sensor_gpu_sim(sentry_gpu: bool) -> None:
    if not sentry_gpu:
        pytest.skip("pass --gpu to run CUDA tests")
    from sentry.sensors.acoustic_sensor import gpu_sim_batch_fft

    r = gpu_sim_batch_fft(batch_size=4096)
    assert r.source.startswith("gpu_fft")
