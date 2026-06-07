#!/usr/bin/env bash
# SENTRY RunPod GPU MELT — force 80-100% GPU utilization. Pi field = CPU only.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export SENTRY_ROOT="${SENTRY_ROOT:-/workspace/fratres-sentry}"
cd "$SENTRY_ROOT"

export SENTRY_FORCE_GPU=1
export SENTRY_MELT_SECONDS="${SENTRY_MELT_SECONDS:-120}"
export SENTRY_MATMUL_DIM="${SENTRY_MATMUL_DIM:-16384}"
export SENTRY_GPU_TARGET_UTIL="${SENTRY_GPU_TARGET_UTIL:-80}"
export SENTRY_GPU_FFT_BATCH="${SENTRY_GPU_FFT_BATCH:-32768}"
export SENTRY_GPU_MC_TOTAL="${SENTRY_GPU_MC_TOTAL:-500000}"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  SENTRY run_melt_pod.sh — FORCE GPU MELT                     ║"
echo "║  Pi field deploy: CPU-only. This script: burn rented GPU.     ║"
echo "╚══════════════════════════════════════════════════════════════╝"

python3 -m pip install -U pip -q
python3 -m pip install -e "implementation/.[dev,gpu]" -q 2>/dev/null \
  || python3 -m pip install -e "implementation/.[dev]" -q

python3 -m pip install torch --index-url https://download.pytorch.org/whl/cu124 -q

echo ""
echo "=== CUDA probe ==="
python3 -c "
import torch
print('CUDA available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('Device:', torch.cuda.get_device_name(0))
    x = torch.randn(8192, 8192, device='cuda', dtype=torch.float16)
    for i in range(5):
        x = torch.mm(x, x[:8192])
    torch.cuda.synchronize()
    print('Warmup matmul OK, mem GB:', round(torch.cuda.max_memory_allocated()/1e9, 2))
"

echo ""
echo "=== nvidia-smi BEFORE ==="
nvidia-smi

echo ""
echo "=== GPU STRESS TEST (${SENTRY_MELT_SECONDS}s, matmul ${SENTRY_MATMUL_DIM}) ==="
export PYTHONPATH="${SENTRY_ROOT}/implementation/src"
python3 -m sentry.simulation.stress_test \
  --duration "$SENTRY_MELT_SECONDS" \
  --matmul-dim "$SENTRY_MATMUL_DIM" \
  --output validation/reports/gpu-stress-test.json

echo ""
echo "=== GPU batch FFT (32k streams) ==="
PYTHONPATH="${SENTRY_ROOT}/implementation/src" python3 -c "
from sentry.gpu.acoustic_batch import gpu_batch_fft_propeller
r = gpu_batch_fft_propeller()
import json; print(json.dumps(r.__dict__, indent=2))
"

echo ""
echo "=== GPU Monte Carlo (500k vectorized) ==="
PYTHONPATH="${SENTRY_ROOT}/implementation/src" python3 -c "
from sentry.gpu.monte_carlo import gpu_monte_carlo_fusion
r = gpu_monte_carlo_fusion()
import json; print(json.dumps({'total': r.total_scenarios, 'levels': r.level_counts, 'elapsed_s': r.elapsed_s}, indent=2))
"

echo ""
echo "=== Infinite matmul burn (120s cap) ==="
timeout 120 python3 -c "
import torch, time
print('CUDA:', torch.cuda.is_available())
x = torch.randn(10000, 10000, device='cuda', dtype=torch.float16)
t0 = time.time()
while time.time() - t0 < 115:
    x = torch.mm(x, x.t())
torch.cuda.synchronize()
print('Infinite matmul segment complete')
" || true

echo ""
echo "=== pytest (CPU logic, post-GPU) ==="
PYTHONPATH="${SENTRY_ROOT}/implementation/src" python3 -m pytest implementation/tests/ -q --tb=line -k "not gpu" 2>/dev/null \
  || PYTHONPATH="${SENTRY_ROOT}/implementation/src" python3 -m pytest implementation/tests/ -q --tb=line -k "not gpu"

echo ""
echo "=== pytest --gpu (CUDA batches) ==="
PYTHONPATH="${SENTRY_ROOT}/implementation/src" python3 -m pytest implementation/tests/test_gpu.py --gpu -q --tb=line || true

echo ""
echo "=== nvidia-smi AFTER ==="
nvidia-smi

echo ""
echo "=== MELT REPORT ==="
cat validation/reports/gpu-stress-test.json
