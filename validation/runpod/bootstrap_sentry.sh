#!/usr/bin/env bash
# SENTRY RunPod full bootstrap — install, test, mass validation, readiness report
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/runpod_env.sh"
cd "$SENTRY_ROOT"

echo "=== SENTRY RunPod bootstrap ==="
echo "ROOT=$SENTRY_ROOT VCPU=$SENTRY_VCPU WORKERS=$SENTRY_WORKERS nproc=$(nproc)"
echo "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'none')"

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  python3 python3-pip python3-venv git rtl-sdr librtlsdr-dev portaudio19-dev \
  > /dev/null 2>&1 || true

python3 -m pip install -U pip setuptools wheel -q
python3 -m pip install -e "implementation/.[dev]" -q

echo "=== pytest ==="
python3 -m pytest implementation/tests/ -q --tb=line

echo "=== defense audit ==="
python3 run_complete_audit.py

echo "=== mass validation ($SENTRY_MASS_SCENARIOS scenarios, $SENTRY_WORKERS workers) ==="
python3 validation/runpod/run_mass_validation.py

echo "=== OK SENTRY pod bootstrap complete ==="
echo "Reports: $SENTRY_ROOT/validation/reports/"
