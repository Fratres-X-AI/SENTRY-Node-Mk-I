# SENTRY Node Mk I - Published Test Results

**Generated:** 2026-07-19T21:30:25.817803+00:00  
**Source:** committed-snapshot  
**Overall:** PASS  
**Version:** 0.5.0-darkspace-integrated

This directory is committed on purpose so validation evidence is visible in the
repository (not only as ephemeral GitHub Actions artifacts).

## Gate summary

| Gate | Result | Detail |
|------|--------|--------|
| Pytest | PASS | 38/38 in 51.513s |
| Coverage (measured include set) | PASS | 100.0% / 47/47 lines |
| Mypy (strict) | PASS | 46 files / 0 errors |
| Simulation smoke | PASS | intrusion path |
| Build readiness | PASS | software gate |
| Defense readiness audit | PASS | overall PASS |

## Scenario battery

| Scenario | Status | Frames | Max level | Mean CPU % | Mean W | Audit chain |
|----------|--------|--------|-----------|------------|--------|-------------|
| benign | PASS | 41 | CLEAR | 50.1 | 3.3 | valid |
| intrusion | PASS | 41 | RED | 46.6 | 3.3 | valid |
| jamming | PASS | 41 | HOLD | 41.3 | 3.3 | valid |
| low_visibility | PASS | 41 | YELLOW | 35.8 | 3.3 | valid |

## Failure modes

| Mode | Passed | Max level | Detail |
|------|--------|-----------|--------|
| sensor_dropout_rf | True | YELLOW | max_level=YELLOW |
| thermal_throttle_jamming | True | HOLD | max_level=HOLD |
| tamper_during_intrusion | True | HOLD | max_level=HOLD |
| low_power_duty_cycle | True | CLEAR | active=True sleep=False |
| deployment_chain_break | True | CLEAR | operational=0/8 |
| deployment_entanglement | True | CLEAR | failed_join=6/6 |
| deployment_antenna_damage | True | CLEAR | passed=0/4 |
| deployment_alert_suppression | True | CLEAR | max_level=CLEAR phase=deployed |

## Machine-readable artifacts in this folder

- `summary.json` - gate rollup
- `pytest-junit.xml` - pytest JUnit
- `coverage.xml` - coverage.xml
- `defense-readiness-sentry.json` - full audit (paths sanitized)
- `mypy.txt`, `simulation.txt`, `build_readiness.txt`, `audit.txt` - gate logs

## Reproduce

```bash
python scripts/collect_ci_reports.py
python scripts/publish_results.py
```
