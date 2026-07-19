# Contributing

Thanks for improving SENTRY.

## Ground Rules

- Keep the project defensive (passive sensing + short LoRa alert relay only).
- Do not add offensive, kinetic, jamming, targeting, or autonomous response behavior.
- Do not commit secrets, generated reports, caches, model weights, or hardware-specific credentials.
- Keep Pi Zero 2 W constraints in mind: low RAM, low power, headless operation.

## Local Checks

From the repo root:

```bash
cd implementation
pip install -e ".[dev]"
pytest tests --cov=sentry --cov-fail-under=100 -q -k "not gpu"
mypy src/sentry
cd ..
python validation/build_readiness.py
python run_complete_audit.py
```

To regenerate the same report bundle CI uploads:

```bash
python scripts/collect_ci_reports.py
```

Outputs land in `validation/reports/ci/` (gitignored). On GitHub, download them from **Actions → run → Artifacts → `sentry-ci-reports-<run_id>`**.

## Pull Requests

PRs should include:

- Clear summary
- Risk notes for hardware or security changes
- Tests for changed behavior
- Updated docs when commands, wiring, configs, or outputs change
