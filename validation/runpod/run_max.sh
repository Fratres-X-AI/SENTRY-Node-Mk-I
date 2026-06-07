#!/usr/bin/env bash
# SENTRY RunPod MAX — full burn: pytest, audit, 100k Monte Carlo, GPU acoustic, mesh soak
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/runpod_env.sh"
cd "$SENTRY_ROOT"

export SENTRY_WORKERS="${SENTRY_WORKERS:-120}"
export SENTRY_MASS_SCENARIOS="${SENTRY_MASS_SCENARIOS:-25000}"
export SENTRY_MASS_FRAMES="${SENTRY_MASS_FRAMES:-40}"
export SENTRY_MESH_ALERTS="${SENTRY_MESH_ALERTS:-5000}"

echo "=============================================="
echo " SENTRY RUNPOD MAX"
echo " WORKERS=$SENTRY_WORKERS MASS=$((SENTRY_MASS_SCENARIOS * 4)) runs"
echo " GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo none)"
echo " CPU: $(nproc) threads"
echo "=============================================="

python3 -m pip install -U pip -q
python3 -m pip install -e "implementation/.[dev]" -q
python3 -m pip install torch --index-url https://download.pytorch.org/whl/cu124 -q 2>/dev/null \
  || python3 -m pip install torch -q

echo "=== [1/5] pytest ==="
python3 -m pytest implementation/tests/ -q --tb=line

echo "=== [2/5] defense audit ==="
python3 run_complete_audit.py | tail -1

echo "=== [3/5] mass Monte Carlo ($(( SENTRY_MASS_SCENARIOS * 4 )) runs) ==="
python3 validation/runpod/run_mass_validation.py

echo "=== [4/5] GPU acoustic classifier ==="
python3 validation/runpod/run_gpu_acoustic.py

echo "=== [5/5] 4-node mesh soak ($(( SENTRY_MESH_ALERTS * 4 )) alerts) ==="
python3 validation/runpod/run_mesh_soak.py

python3 <<'PY'
import json
from pathlib import Path
root = Path("validation/reports")
parts = {}
for name in [
    "defense-readiness-sentry.json",
    "runpod-mass-validation.json",
    "runpod-gpu-acoustic.json",
    "runpod-mesh-soak.json",
]:
    p = root / name
    if p.exists():
        parts[name] = json.loads(p.read_text())
summary = {
    "codename": "SENTRY",
    "mode": "runpod_max_summary",
    "reports": parts,
    "overall": "PASS" if all(
        parts.get(n, {}).get("overall", parts.get(n, {}).get("acceptance", {}).get("pass", True))
        in (True, "PASS", None)
        for n in parts
    ) else "FAIL",
}
out = root / "runpod-max-summary.json"
out.write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({"overall": summary["overall"], "reports_written": list(parts)}, indent=2))
PY

echo "=== SENTRY RUNPOD MAX COMPLETE ==="
ls -la validation/reports/runpod*.json validation/reports/defense-readiness*.json 2>/dev/null || true
