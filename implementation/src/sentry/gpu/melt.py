"""Sustained GPU melt with nvidia-smi utilization sampling."""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field

from sentry.gpu.acoustic_batch import gpu_batch_fft_propeller
from sentry.gpu.device import require_cuda
from sentry.gpu.monte_carlo import gpu_monte_carlo_fusion


def sample_gpu_utilization() -> dict[str, float | int | str]:
    """Parse nvidia-smi utilization.gpu and memory.used."""
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        ).strip()
        parts = [p.strip() for p in out.split(",")]
        return {
            "gpu_util_pct": float(parts[0]) if parts else 0.0,
            "mem_util_pct": float(parts[1]) if len(parts) > 1 else 0.0,
            "mem_used_mib": float(parts[2]) if len(parts) > 2 else 0.0,
            "mem_total_mib": float(parts[3]) if len(parts) > 3 else 0.0,
            "temp_c": float(parts[4]) if len(parts) > 4 else 0.0,
            "power_w": float(parts[5]) if len(parts) > 5 else 0.0,
        }
    except (subprocess.SubprocessError, FileNotFoundError, ValueError, IndexError):
        return {"gpu_util_pct": -1.0, "error": "nvidia-smi unavailable"}


@dataclass
class GpuMeltEngine:
    """Orchestrates sustained heavy CUDA workloads until target utilization is proven."""

    duration_s: float = 90.0
    matmul_dim: int = 12288
    samples: list[dict] = field(default_factory=list)

    def _matmul_burn_until(self, until: float) -> None:
        import torch

        device = require_cuda()
        n = self.matmul_dim
        a = torch.randn(n, n, device=device, dtype=torch.float16)
        b = torch.randn(n, n, device=device, dtype=torch.float16)
        while time.perf_counter() < until:
            a = torch.mm(a, b)
        torch.cuda.synchronize()

    def _poll_utilization(self, stop: threading.Event, interval_s: float = 0.15) -> None:
        while not stop.is_set():
            util = sample_gpu_utilization()
            self.samples.append({"ts": time.perf_counter(), **util})
            stop.wait(interval_s)

    def run(self) -> dict:
        import os

        import torch

        require_cuda()
        name = torch.cuda.get_device_name(0)
        target_util = float(os.environ.get("SENTRY_GPU_TARGET_UTIL", 80))
        chunk_s = float(os.environ.get("SENTRY_MELT_CHUNK_S", 12.0))

        t_end = time.perf_counter() + self.duration_s
        iteration = 0
        phase_results: list[dict] = []

        print(f"SENTRY GPU MELT: {name} target>={target_util}% for {self.duration_s}s")
        print("BLUNT: GPU melt is RunPod dev only — Pi Zero 2 W field node is CPU-only <5W.")

        stop_poll = threading.Event()
        poll_thread = threading.Thread(target=self._poll_utilization, args=(stop_poll,), daemon=True)
        poll_thread.start()

        try:
            while time.perf_counter() < t_end:
                iteration += 1
                chunk_end = min(time.perf_counter() + chunk_s, t_end)
                self._matmul_burn_until(chunk_end)

                if iteration % 2 == 0:
                    fft_r = gpu_batch_fft_propeller()
                    phase_results.append({"fft": fft_r.__dict__})

                if iteration % 3 == 0:
                    mc_r = gpu_monte_carlo_fusion(
                        total=int(os.environ.get("SENTRY_GPU_MC_TOTAL", 200_000)),
                        batch=65536,
                    )
                    phase_results.append({"monte_carlo": mc_r.__dict__})

                if iteration % 4 == 0:
                    util = sample_gpu_utilization()
                    print(
                        f"  iter={iteration} gpu_util={util.get('gpu_util_pct')}% "
                        f"mem={util.get('mem_used_mib')}MiB power={util.get('power_w')}W"
                    )
        finally:
            stop_poll.set()
            poll_thread.join(timeout=2.0)

        utils = [
            float(s["gpu_util_pct"])
            for s in self.samples
            if isinstance(s.get("gpu_util_pct"), (int, float)) and float(s["gpu_util_pct"]) >= 0
        ]
        max_util = max(utils) if utils else 0.0
        mean_util = sum(utils) / len(utils) if utils else 0.0
        passed = max_util >= target_util

        report = {
            "codename": "SENTRY",
            "mode": "gpu_melt_engine",
            "device": name,
            "duration_s": self.duration_s,
            "iterations": iteration,
            "util_samples": len(utils),
            "gpu_util_max_pct": round(max_util, 1),
            "gpu_util_mean_pct": round(mean_util, 1),
            "target_util_pct": target_util,
            "target_met": passed,
            "matmul_dim": self.matmul_dim,
            "phase_results_count": len(phase_results),
            "field_note": "GPU irrelevant for Pi deployment — CPU duty-cycled only",
            "overall": "PASS" if passed else "FAIL",
        }
        return report
