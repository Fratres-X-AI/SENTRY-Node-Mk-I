#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/runpod_env.sh"
cd "$SENTRY_ROOT"
python3 -m pytest implementation/tests/ -q
python3 run_complete_audit.py
echo "OK SENTRY smoke CI"
