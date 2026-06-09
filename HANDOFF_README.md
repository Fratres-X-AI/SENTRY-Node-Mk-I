# SENTRY — Handoff Package (AN/GSQ-100(V)1)

**Codename:** SENTRY · **Type:** AN/GSQ-100(V)1 · SENTRY Node Mk I · **Version:** v0.4.0-build  
**Organization:** Fratres X AI — Defense Projects HQ · **Mode:** Defensive-only · Receive-only

---

> **THIS PACKAGE IS DESIGNED FOR A BUILDER WHO IS NOT THE ORIGINAL DEVELOPER.**
> **Follow every checklist in strict order. Do not improvise.**
> If a step fails, stop and consult [`docs/known_first_build_failures.md`](docs/known_first_build_failures.md) before continuing.

---

## What SENTRY is (plain language)

A small, pole-mounted, weatherproof box built on a **Raspberry Pi Zero 2 W**. It **passively listens** for intruders using motion (PIR), sound (microphone, 100–500 Hz), and radio energy (RTL-SDR). It scores a threat level (**CLEAR → YELLOW → ORANGE → RED → HOLD**), keeps a tamper-evident log, and relays alerts to other nodes over a **Meshtastic LoRa** mesh.

**It does not transmit jamming. It does not fire anything. It has no offensive function.** It is an early-warning sensor for soldier safety.

---

## Scope — what is INCLUDED

| Included | Notes |
|----------|-------|
| Full Python software stack | Fusion, scoring, guardian FSM, HMAC audit, mesh relay |
| Pi Zero 2 W drivers | PIR, tamper, acoustic FFT, RTL-SDR sweep, Meshtastic |
| 4-node site configs | `configs/nodes/sentry-pi-zero-00X.json` |
| Procurement BOM | `configs/procurement_bom.json` (~$216/node) |
| Assembly + flash + gate docs | This package |
| Acceptance gates G1–G5 | `python validation/run_gate.py --gate G1..G5` |
| CI (GitHub Actions) | Green on `main` |

## Scope — what is EXCLUDED / NOT VALIDATED

| Excluded / limited | Reality — state this to stakeholders |
|--------------------|--------------------------------------|
| **5.8 GHz RF** | **Synthetic only.** RTL-SDR V3 (RTL2832U) cannot tune 5.8 GHz. Do not claim 5.8 GHz detection. |
| **Meshtastic RX** | **Manual / phone app.** Outbound alerts (TX) work; inbound receive is a spool placeholder, confirmed via the Meshtastic app. |
| **Chain/rocket deployment** | **Paper concept only.** Mk I requires **hand emplacement**. See [`docs/deployment_chain.md`](docs/deployment_chain.md). |
| **Field FP/FN rates** | **Unmeasured.** Simulation ≠ field performance. |
| **Export / ITAR** | **Review required** before any international shipment, sale, or foreign disclosure. See [`docs/export_screening.md`](docs/export_screening.md). |
| **Field validation (G1–G5)** | **Not executed** — requires physical hardware. |

---

## One-page quick start

```
STEP 1  ORDER PARTS
        Open configs/procurement_bom.json
        Order ONE node + spares first (~$332). Do not buy 4x yet.
        Heed every "risk_notes" field (TCXO RTL-SDR, SX1262 T-Beam).

STEP 2  BUILD NODE 001
        Follow docs/build_assembly.md exactly (GPIO pins, wire colors, power-on sequence).
        Flash the SD card with docs/sd_flash_checklist.md.

STEP 3  RUN G1 (single command, on the Pi)
        cd /opt/sentry-node-mk-i
        sudo bash deploy/bootstrap_pi_zero.sh
        sentry-guard --probe --node-config /etc/sentry/node_config.json
        # OR equivalently:
        python validation/run_gate.py --gate G1

STEP 4  REPORT RESULTS
        Copy the JSON from validation/reports/gate-g1.json.
        If pass=false, open docs/known_first_build_failures.md and apply the exact fix.
        Do NOT proceed to G2 until G1 pass=true.
```

After G1 passes on node 001: continue to **G2–G5** in [`docs/gate_execution.md`](docs/gate_execution.md), then duplicate the node ×3.

---

## Directory map and file purpose

| Path | Purpose |
|------|---------|
| `HANDOFF_README.md` | **This file** — start here |
| `HANDOFF_CHECKLIST.md` | Author sign-off before declaring handoff complete |
| `docs/BUILD_STAGE.md` | **Single source of truth** for the build process + first/next-node decision tree |
| `docs/build_assembly.md` | Physical assembly: pins, wires, torque, power-on voltages, mistakes |
| `docs/sd_flash_checklist.md` | Literal checkbox flash + OS config + udev + Meshtastic |
| `docs/gate_execution.md` | G1–G5 commands, expected output, troubleshooting trees |
| `docs/known_first_build_failures.md` | Every anticipated first-build failure + exact fix |
| `docs/deployment_chain.md` | Hand-emplacement spacing + mesh formation (chain = paper only) |
| `docs/system_datasheet.md` | Full hardware/electrical/RF/power spec |
| `docs/bom_dimensions.md` | Part dimensions and masses |
| `docs/outputs_icd.md` | All JSON output schemas |
| `docs/risk_register.md` | Blunt risk list R1–R14 |
| `docs/pi_deployment.md` | Pi install + systemd notes |
| `docs/export_screening.md` | Export/ITAR screening draft |
| `configs/procurement_bom.json` | Frozen shopping list with risk/qty/sourcing |
| `configs/nodes/*.json` | Per-node production configs (simulation OFF) |
| `configs/deployment_site_alpha.json` | Example 4-node site manifest |
| `configs/sentry_mission_profile.json` | Thresholds, weights, guardian timing |
| `deploy/bootstrap_pi_zero.sh` | One-shot Pi provisioning |
| `deploy/sentry-guardian.service` | systemd unit |
| `deploy/99-sentry.rules` | udev rules (RTL-SDR, Meshtastic, USB audio) |
| `validation/run_gate.py` | **G1–G5 gate runner** (run on the Pi) |
| `validation/build_readiness.py` | Software build gate (run anywhere) |
| `validation/generate_node_configs.py` | Regenerate per-node configs from site manifest |
| `implementation/src/sentry/` | Source: fusion, scoring, guardian, sensors, deployment, networking |
| `implementation/tests/` | pytest suite (CI) |
| `validation/reports/` | Generated gate + audit artifacts |

---

## Defensive-only statement (binding)

SENTRY is a **passive, receive-only early-warning system**. No transmit countermeasures, no kinetic logic, no autonomous response. **Human-on-loop is assumed for every alert.** Any change that adds transmit/jam/engage capability is **out of scope** and requires fresh export and legal review.
