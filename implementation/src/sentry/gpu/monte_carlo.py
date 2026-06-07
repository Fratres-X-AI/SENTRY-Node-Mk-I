"""GPU-parallel Monte Carlo threat fusion (RunPod dev only)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from sentry.gpu.device import require_cuda


@dataclass
class GpuMonteCarloResult:
    total_scenarios: int
    level_counts: dict[str, int]
    mean_threat: float
    device: str
    elapsed_s: float
    batches: int


def _level_from_score(scores, yellow, orange, red):
    import torch

    levels = torch.zeros_like(scores, dtype=torch.int64)
    levels = torch.where(scores >= yellow, torch.ones_like(levels), levels)
    levels = torch.where(scores >= orange, torch.full_like(levels, 2), levels)
    levels = torch.where(scores >= red, torch.full_like(levels, 3), levels)
    return levels


def gpu_monte_carlo_fusion(
    total: int | None = None,
    batch: int | None = None,
) -> GpuMonteCarloResult:
    """
    Vectorized fusion + scoring on GPU tensors.
    Simulates passive channel fusion at massive batch scale.
    """
    import time

    import torch

    device = require_cuda()
    total = total or int(os.environ.get("SENTRY_GPU_MC_TOTAL", 500_000))
    batch = batch or int(os.environ.get("SENTRY_GPU_MC_BATCH", 65536))

    w = torch.tensor([0.30, 0.25, 0.20, 0.25], device=device)
    yellow, orange, red = 0.35, 0.55, 0.75
    names = ["CLEAR", "YELLOW", "ORANGE", "RED"]
    counts = {n: 0 for n in names}
    counts["HOLD"] = 0
    threat_sum = 0.0
    batches = 0
    t0 = time.perf_counter()

    remaining = total
    while remaining > 0:
        n = min(batch, remaining)
        # [B, 4] channels: pir, acoustic, rf, visual
        ch = torch.rand(n, 4, device=device)
        # intrusion/jamming injection
        scenario_roll = torch.rand(n, device=device)
        jam = scenario_roll > 0.75
        intr = (scenario_roll > 0.25) & (scenario_roll <= 0.75)
        ch[:, 0] = torch.where(intr, ch[:, 0] * 0.5 + 0.5, ch[:, 0] * 0.15)
        ch[:, 1] = torch.where(intr, ch[:, 1] * 0.5 + 0.4, ch[:, 1] * 0.1)
        ch[:, 2] = torch.where(jam, torch.ones_like(ch[:, 2]) * 0.95, ch[:, 2] * 0.2)
        ch[:, 3] = torch.where(intr, ch[:, 3] * 0.5 + 0.35, ch[:, 3] * 0.1)

        scores = (ch * w).sum(dim=1)
        scores = torch.clamp(scores, 0, 1)
        levels = _level_from_score(scores, yellow, orange, red)
        hold = jam & (scores >= orange)
        levels = torch.where(hold, torch.full_like(levels, 4), levels)

        for idx, name in enumerate(names):
            counts[name] += int((levels == idx).sum().item())
        counts["HOLD"] += int((levels == 4).sum().item())
        threat_sum += float(scores.sum().item())

        # Extra GPU pressure: large matmul slice
        if batches % 4 == 0:
            m = min(4096, n)
            x = torch.randn(m, m, device=device)
            x = torch.mm(x, x)

        remaining -= n
        batches += 1

    elapsed = time.perf_counter() - t0
    return GpuMonteCarloResult(
        total_scenarios=total,
        level_counts=counts,
        mean_threat=threat_sum / total,
        device=str(device),
        elapsed_s=round(elapsed, 4),
        batches=batches,
    )
