"""GPU Monte Carlo for chain deployment impact survival (RunPod dev)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from sentry.deployment.config import COMPONENT_SURVIVAL_G, ChainDeploymentConfig
from sentry.deployment.physics import LAUNCH_PEAK_G, LaunchMethod


@dataclass
class DeploymentMonteCarloResult:
    total_scenarios: int
    full_chain_survival_rate: float
    mean_operational_nodes: float
    entanglement_rate: float
    antenna_fail_rate: float
    battery_rupture_rate: float
    method: str
    device: str
    elapsed_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_scenarios": self.total_scenarios,
            "full_chain_survival_rate": round(self.full_chain_survival_rate, 4),
            "mean_operational_nodes": round(self.mean_operational_nodes, 2),
            "entanglement_rate": round(self.entanglement_rate, 4),
            "antenna_fail_rate": round(self.antenna_fail_rate, 4),
            "battery_rupture_rate": round(self.battery_rupture_rate, 4),
            "method": self.method,
            "device": self.device,
            "elapsed_s": round(self.elapsed_s, 4),
        }


def _run_cpu_monte_carlo(
    total: int,
    config: ChainDeploymentConfig,
    method: LaunchMethod,
) -> DeploymentMonteCarloResult:
    import random
    import time

    t0 = time.perf_counter()
    launch_peak = LAUNCH_PEAK_G[method]
    pi_g = COMPONENT_SURVIVAL_G["pi_zero_2w"]
    rtl_g = COMPONENT_SURVIVAL_G["rtl_sdr_v3"]
    mic_g = COMPONENT_SURVIVAL_G["mems_mic"]
    bat_g = COMPONENT_SURVIVAL_G["lipo_2s"]

    full_survive = 0
    op_sum = 0.0
    entangle_n = 0
    antenna_fail_n = 0
    battery_n = 0
    rng = random.Random(99)

    for _ in range(total):
        op = 0
        for i in range(config.node_count):
            whip = 1.0 - 0.12 * (i / max(config.node_count - 1, 1))
            vel = min(1.0, config.launch_velocity_m_s / 25.0)
            peak = launch_peak * whip * (0.85 + 0.15 * vel)
            peak *= 1.0 + rng.gauss(0, 0.08)
            if peak <= pi_g and peak <= rtl_g and peak <= mic_g and peak <= bat_g:
                if rng.random() >= config.entanglement_prior_per_node:
                    if rng.random() < config.antenna_deploy_success_prior:
                        if rng.random() >= 0.04:
                            op += 1
                        else:
                            battery_n += 1
                    else:
                        antenna_fail_n += 1
                else:
                    entangle_n += 1
        op_sum += op
        if op == config.node_count:
            full_survive += 1

    elapsed = time.perf_counter() - t0
    n = total * config.node_count
    return DeploymentMonteCarloResult(
        total_scenarios=total,
        full_chain_survival_rate=full_survive / total,
        mean_operational_nodes=op_sum / total,
        entanglement_rate=entangle_n / n,
        antenna_fail_rate=antenna_fail_n / n,
        battery_rupture_rate=battery_n / n,
        method=method.value,
        device="cpu",
        elapsed_s=elapsed,
    )


def gpu_monte_carlo_deployment(
    total: int | None = None,
    config: ChainDeploymentConfig | None = None,
    method: str | LaunchMethod = LaunchMethod.PNEUMATIC_SOFT,
) -> DeploymentMonteCarloResult:
    """
    Vectorized Monte Carlo for chain deployment outcomes.
    Uses CUDA when available; CPU fallback on Pi / CI.
    """
    import time

    config = config or ChainDeploymentConfig()
    total = total or int(os.environ.get("SENTRY_DEPLOY_MC_TOTAL", 50_000))
    if isinstance(method, str):
        try:
            method = LaunchMethod(method)
        except ValueError:
            method = LaunchMethod.PNEUMATIC_SOFT

    try:
        import torch
        from sentry.gpu.device import get_device

        device = get_device(force_gpu=os.environ.get("SENTRY_FORCE_GPU", "") == "1")
        if device.type != "cuda":
            raise RuntimeError("CUDA not selected")

        t0 = time.perf_counter()
        launch_peak = LAUNCH_PEAK_G[method]
        pi_g = COMPONENT_SURVIVAL_G["pi_zero_2w"]
        rtl_g = COMPONENT_SURVIVAL_G["rtl_sdr_v3"]
        mic_g = COMPONENT_SURVIVAL_G["mems_mic"]
        bat_g = COMPONENT_SURVIVAL_G["lipo_2s"]
        nc = config.node_count

        idx = torch.arange(nc, device=device, dtype=torch.float32)
        whip = 1.0 - 0.12 * (idx / max(nc - 1, 1))
        vel = min(1.0, config.launch_velocity_m_s / 25.0)

        full_survive = 0
        op_sum = 0.0
        entangle_n = 0
        antenna_fail_n = 0
        battery_n = 0
        batch = min(8192, total)

        for start in range(0, total, batch):
            n = min(batch, total - start)
            noise = 1.0 + 0.08 * torch.randn(n, nc, device=device)
            peak = launch_peak * whip.unsqueeze(0) * (0.85 + 0.15 * vel) * noise
            survive = (
                (peak <= pi_g)
                & (peak <= rtl_g)
                & (peak <= mic_g)
                & (peak <= bat_g)
            )
            entangle = torch.rand(n, nc, device=device) < config.entanglement_prior_per_node
            antenna = torch.rand(n, nc, device=device) < config.antenna_deploy_success_prior
            battery = torch.rand(n, nc, device=device) < 0.04
            operational = survive & ~entangle & antenna & ~battery
            op_count = operational.sum(dim=1)
            full_survive += int((op_count == nc).sum().item())
            op_sum += float(op_count.sum().item())
            entangle_n += int((survive & entangle).sum().item())
            antenna_fail_n += int((survive & ~entangle & ~antenna).sum().item())
            battery_n += int((survive & battery).sum().item())
            _ = torch.mm(
                peak[: min(256, n)],
                peak[: min(256, n)].T,
            )

        elapsed = time.perf_counter() - t0
        node_samples = total * nc
        return DeploymentMonteCarloResult(
            total_scenarios=total,
            full_chain_survival_rate=full_survive / total,
            mean_operational_nodes=op_sum / total,
            entanglement_rate=entangle_n / node_samples,
            antenna_fail_rate=antenna_fail_n / node_samples,
            battery_rupture_rate=battery_n / node_samples,
            method=method.value,
            device=str(device),
            elapsed_s=elapsed,
        )
    except Exception:
        return _run_cpu_monte_carlo(total, config, method)
