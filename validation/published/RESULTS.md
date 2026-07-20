# SENTRY Node Mk I - Validation Evidence

**Maturity:** software-gate prototype (pre-physical)  
**Version:** `0.5.0-darkspace-integrated`  
**Snapshot:** 2026-07-19T21:30:25.817803+00:00  
**Overall software gates:** PASS  

Fratres X AI standard: physics first, reviewable gates, conservative claims.
This folder is committed evidence - not marketing copy.

## What this proves

| Claim | Status | Evidence |
|-------|--------|----------|
| Threat scoring responds correctly across benign / intrusion / jamming / low-vis | Proven in simulation | Scenario battery below |
| HMAC audit chain detects tampering and remains valid on clean runs | Proven in CI/sim | Audit + tamper probe |
| Strict typing holds on the Python package | Proven | Mypy gate |
| Unit tests for the measured core pass | Proven | Pytest gate |
| Mean simulated power stays under the 5 W target | Proven in sim | Scenario power columns |
| Field FP/FN, RF front-end performance, Pi GPIO/USB stack | **Not proven** | Requires G1-G5 hardware gates |
| Chain-deploy / high-g launch survival for COTS Pi nodes | **Not a product claim** | Stress sims show near-zero survival - by design |

## How to read this report

- **Scenario PASS** means the guardian reached the expected alert class and kept a valid audit chain.
- **Failure-mode PASS** means the software correctly handled injected degradation. Counts like `0/8 operational` are expected outcomes under destructive stress - not a silent product failure.
- **Coverage 100%** applies only to the **measured include set** (currently 47 statements). Hardware, GPU, and deployment modules omitted from the fail-under gate are not claimed covered.

## Gate summary

| Gate | Result | Detail |
|------|--------|--------|
| Pytest | PASS | 38/38 in 51.513 s |
| Coverage (include set) | PASS | 100.0% of 47 measured lines |
| Mypy (strict) | PASS | 46 files, 0 errors |
| Simulation smoke | PASS | intrusion path, audit valid |
| Build readiness (software) | PASS | required files + site layout |
| Defense readiness audit | PASS | overall PASS |

## Scenario battery (expected behavior)

| Scenario | Result | Max level | Mean CPU % | Mean W | Audit |
|----------|--------|-----------|------------|--------|-------|
| benign | PASS | CLEAR | 50.1 | 3.3 | valid |
| intrusion | PASS | RED | 46.6 | 3.3 | valid |
| jamming | PASS | HOLD | 41.3 | 3.3 | valid |
| low_visibility | PASS | YELLOW | 35.8 | 3.3 | valid |

Interpretation: quiet scene stays CLEAR; intrusion escalates; jamming forces HOLD;
degraded visibility stays elevated but not catastrophic.

## Resilience battery (injected faults)

These cases pass when the node **refuses to lie** under bad conditions.

| Mode | Gate | Observed | Meaning |
|------|------|----------|---------|
| sensor_dropout_rf | PASS | max_level=YELLOW | RF loss degrades confidence; does not fabricate RED |
| thermal_throttle_jamming | PASS | max_level=HOLD | Thermal + jamming enters safe HOLD |
| tamper_during_intrusion | PASS | max_level=HOLD | Tamper dominates; HOLD wins |
| low_power_duty_cycle | PASS | active=True sleep=False | Power discipline retained |
| deployment_chain_break | PASS | operational=0/8 | Broken chain reported as non-operational |
| deployment_entanglement | PASS | failed_join=6/6 | Entangled nodes do not fake mesh readiness |
| deployment_antenna_damage | PASS | passed=0/4 | Damaged antennas fail BIT honestly |
| deployment_alert_suppression | PASS | max_level=CLEAR phase=deployed | Alerts suppressed until operational phase |

## Explicit non-claims

- Not field-validated. No outdoor FP/FN study yet.
- RTL-SDR Blog V4 is not a native 2.4/5.8 GHz solution; high-band paths remain conversion/synthetic until a real front-end is qualified.
- Meshtastic RX remains a conservative spool/integration path.
- High-g / line-charge reference sims destroy COTS Pi stacks - that result is a physics boundary, not a shipping promise.

## Machine-readable artifacts

| File | Contents |
|------|----------|
| `summary.json` | Gate rollup |
| `pytest-junit.xml` | Pytest JUnit |
| `coverage.xml` | Coverage for the measured include set |
| `defense-readiness-sentry.json` | Full audit (local paths sanitized) |
| `mypy.txt` / `simulation.txt` / `build_readiness.txt` / `audit.txt` | Gate logs |

## Reproduce

```bash
python scripts/collect_ci_reports.py
python scripts/publish_results.py
```

CI also uploads `sentry-ci-reports-<run_id>` on every green Actions run.
