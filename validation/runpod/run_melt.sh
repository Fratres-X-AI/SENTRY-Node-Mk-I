#!/usr/bin/env bash
# SENTRY MELT MODE — A100 full burn: 1M+ Monte Carlo, 1M GPU train, 400k mesh, parallel stress
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/runpod_env.sh"
cd "$SENTRY_ROOT"

export SENTRY_WORKERS="${SENTRY_WORKERS:-250}"
export SENTRY_MASS_SCENARIOS="${SENTRY_MASS_SCENARIOS:-250000}"
export SENTRY_MASS_FRAMES="${SENTRY_MASS_FRAMES:-40}"
export SENTRY_MESH_ALERTS="${SENTRY_MESH_ALERTS:-100000}"
export SENTRY_MESH_WORKERS="${SENTRY_MESH_WORKERS:-4}"
export SENTRY_GPU_TRAIN_SAMPLES="${SENTRY_GPU_TRAIN_SAMPLES:-1000000}"
export SENTRY_GPU_TEST_SAMPLES="${SENTRY_GPU_TEST_SAMPLES:-100000}"
export SENTRY_TORCH_THREADS="${SENTRY_TORCH_THREADS:-32}"

TOTAL_MC=$((SENTRY_MASS_SCENARIOS * 4))
TOTAL_MESH=$((SENTRY_MESH_ALERTS * 4))

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  SENTRY MELT MODE — A100 BURN                            ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Monte Carlo:  $TOTAL_MC runs @ $SENTRY_WORKERS workers"
echo "║  GPU train:    $SENTRY_GPU_TRAIN_SAMPLES samples"
echo "║  Mesh alerts:  $TOTAL_MESH OMEN payloads"
echo "║  GPU: $(nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo n/a)"
echo "║  CPU threads: $(nproc)"
echo "╚══════════════════════════════════════════════════════════╝"

python3 -m pip install -U pip -q
python3 -m pip install -e "implementation/.[dev]" -q
python3 -m pip install torch --index-url https://download.pytorch.org/whl/cu124 -q 2>/dev/null || python3 -m pip install torch -q

echo ""
echo ">>> [1/6] pytest"
python3 -m pytest implementation/tests/ -q --tb=line

echo ""
echo ">>> [2/6] MELT Monte Carlo ($TOTAL_MC runs)"
T0=$(date +%s)
python3 validation/runpod/run_mass_validation.py
T1=$(date +%s)
echo "    Monte Carlo wall: $((T1-T0))s"

echo ""
echo ">>> [3/6] MELT GPU acoustic ($SENTRY_GPU_TRAIN_SAMPLES samples, A100 CUDA)"
nvidia-smi --query-gpu=utilization.gpu,memory.used,temperature.gpu --format=csv,noheader || true
T0=$(date +%s)
python3 validation/runpod/run_gpu_acoustic.py
T1=$(date +%s)
nvidia-smi --query-gpu=utilization.gpu,memory.used,temperature.gpu --format=csv,noheader || true
echo "    GPU train wall: $((T1-T0))s"

echo ""
echo ">>> [4/6] MELT mesh soak ($TOTAL_MESH alerts)"
T0=$(date +%s)
python3 validation/runpod/run_mesh_soak.py
T1=$(date +%s)
echo "    Mesh wall: $((T1-T0))s"

echo ""
echo ">>> [5/6] SECOND PASS Monte Carlo (stress repeat)"
T0=$(date +%s)
python3 validation/runpod/run_mass_validation.py
T1=$(date +%s)
echo "    Repeat Monte Carlo wall: $((T1-T0))s"

echo ""
echo ">>> [6/6] defense audit + aggregate"
python3 run_complete_audit.py | tail -1
python3 validation/runpod/aggregate_max_reports.py

# Rename reports with melt prefix
for f in runpod-mass-validation.json runpod-gpu-acoustic.json runpod-mesh-soak.json; do
  cp "validation/reports/$f" "validation/reports/melt-$f" 2>/dev/null || true
done

python3 <<'PY'
import json
from pathlib import Path
root = Path("validation/reports")
mass = json.loads((root / "runpod-mass-validation.json").read_text())
gpu = json.loads((root / "runpod-gpu-acoustic.json").read_text())
mesh = json.loads((root / "runpod-mesh-soak.json").read_text())
melt = {
    "codename": "SENTRY",
    "mode": "a100_melt",
    "monte_carlo_runs_per_pass": mass.get("total_runs"),
    "monte_carlo_total_passes": 2,
    "monte_carlo_total_runs": mass.get("total_runs", 0) * 2,
    "monte_carlo_runs_per_second": mass.get("runs_per_second"),
    "gpu_device": gpu.get("device"),
    "gpu_train_samples": gpu.get("train_samples"),
    "gpu_test_accuracy": gpu.get("test_accuracy"),
    "gpu_train_seconds": gpu.get("train_seconds"),
    "mesh_total_alerts": mesh.get("total_sent"),
    "mesh_alerts_per_second": mesh.get("alerts_per_second"),
    "sensor_frames_simulated": mass.get("total_runs", 0) * 2 * 40,
    "overall": "MELT_COMPLETE",
}
(root / "runpod-melt-summary.json").write_text(json.dumps(melt, indent=2) + "\n")
print(json.dumps(melt, indent=2))
PY

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  MELT COMPLETE — A100 survived                           ║"
echo "╚══════════════════════════════════════════════════════════╝"
nvidia-smi || true
