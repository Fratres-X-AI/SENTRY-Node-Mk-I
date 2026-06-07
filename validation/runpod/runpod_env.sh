#!/usr/bin/env bash
# SENTRY RunPod environment — sourced by bootstrap scripts
export SENTRY_ROOT="${SENTRY_ROOT:-/workspace/fratres-sentry}"
export SENTRY_VCPU="${SENTRY_VCPU:-32}"
export SENTRY_WORKERS="${SENTRY_WORKERS:-$(( SENTRY_VCPU > 4 ? SENTRY_VCPU - 2 : 4 ))}"
export SENTRY_MASS_SCENARIOS="${SENTRY_MASS_SCENARIOS:-2000}"
export SENTRY_MASS_SEED_START="${SENTRY_MASS_SEED_START:-1}"
export PYTHONUNBUFFERED=1
