"""SENTRY GPU stress test — sustained 80%+ utilization target."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "implementation" / "src"))

from sentry.gpu.melt import GpuMeltEngine, sample_gpu_utilization  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="SENTRY GPU stress test (RunPod melt)")
    parser.add_argument("--duration", type=float, default=float(os.environ.get("SENTRY_MELT_SECONDS", 90)))
    parser.add_argument("--matmul-dim", type=int, default=int(os.environ.get("SENTRY_MATMUL_DIM", 12288)))
    parser.add_argument("--output", type=Path, default=ROOT / "validation" / "reports" / "gpu-stress-test.json")
    args = parser.parse_args()

    print("nvidia-smi (before):")
    os.system("nvidia-smi --query-gpu=name,utilization.gpu,memory.used,temperature.gpu,power.draw --format=csv")
    print("sample:", sample_gpu_utilization())

    engine = GpuMeltEngine(duration_s=args.duration, matmul_dim=args.matmul_dim)
    report = engine.run()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("\nnvidia-smi (after):")
    os.system("nvidia-smi --query-gpu=name,utilization.gpu,memory.used,temperature.gpu,power.draw --format=csv")
    print(json.dumps(report, indent=2))
    return 0 if report.get("target_met") else 1


if __name__ == "__main__":
    sys.exit(main())
