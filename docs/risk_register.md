# Risk Register — SENTRY Pi Zero 2 W

**Codename:** SENTRY · **Version:** 0.3.0 · **Date:** 7 June 2026

| ID | Risk | Severity | Mitigation (current) | Validation gap |
|----|------|----------|----------------------|----------------|
| R1 | Zero 2 W CPU/RAM overload during rtl_power + SciPy FFT | High | Duty cycle 4s/6s; alternate RF bands | No on-target profiling under load |
| R2 | RTL-SDR V3 cannot receive 5.8 GHz | High | 5g8 synthetic fallback + documented gap | Requires separate 5.8 GHz front-end |
| R3 | Acoustic false positives (wind, traffic) | High | Wind reject heuristic; 100–500 Hz peak filter | No field noise corpus |
| R4 | Meshtastic low throughput / jamming | Medium | OMEN JSON compact payloads; spool fallback | No mesh soak test |
| R5 | Power > 5 W average | Medium | Duty cycling + power_metrics logging | Datasheet estimates only |
| R6 | HMAC audit not tamper-evident in hardware | Medium | GPIO tamper → audit + dry-run wipe | No secure element |
| R7 | Simulation ≠ field EW performance | High | Clearly labeled synthetic V&V | **Bench with 1–2 nodes required** |
| R8 | Export/ITAR for SDR | Medium | [`export_screening.md`](export_screening.md) draft | Counsel sign-off pending |
| R9 | Line-charge / rocket launch shock destroys COTS | **Critical** | **Refused** — sim reference only; pneumatic soft max | No shock-table validation |
| R10 | Connected chain single-point failure | High | Topology model + chain_break failure mode | No field line tensile test |
| R11 | Entanglement on landing | High | Monte Carlo entanglement prior; mesh join fail | No throw trials |
| R12 | Antenna / RTL damage post-landing | High | Post-landing BIT; guardian suppress until operational | No deploy mechanism in BOM |
| R13 | Battery rupture under impact | High | 4% rupture prior in BIT sim | No LiPo abuse test |
| R14 | Deployment adds soldier hazard | **Critical** | Mechanical non-explosive only in scope | Explosive paths explicitly refused |

## Friis range note (planning only)

2.4 GHz passive detection range depends on emitter ERP and local clutter. Use `RfSensor.friis_note()` for **order-of-magnitude** link budget only — not a detection guarantee.

## Soldier safety constraints

- Passive sense only — no transmit counter-jam, no kinetic logic
- Alerts are explainable (rationale string + channel flags)
- HOLD on tamper or jamming suspicion — human-on-loop assumed
