# SENTRY Handoff Completeness Checklist (Author Sign-Off)

**Type:** AN/GSQ-100(V)1 · **Version:** v0.5.0-darkspace-integrated
**Purpose:** The author completes this checklist **before** declaring the handoff package complete.
Every item is verified from the perspective of a builder who has **never seen the code or spoken to the author**.

> Rule: if you cannot tick a box honestly, the package is **not** ready for handoff.

---

## 1. Recipient clarity (no author knowledge assumed)

- [ ] `HANDOFF_README.md` states plainly it is for a non-author builder, with the "do not improvise" rule.
- [ ] Scope (included/excluded) lists 5.8 GHz synthetic, Meshtastic RX manual, chain paper-only, export review.
- [ ] One-page quick start (order → build → G1 → report) is present and ordered.
- [ ] Directory map covers every top-level file/folder a builder will touch.
- [ ] No step says "obviously", "just", or assumes prior context.

## 2. Build process single source of truth

- [ ] `docs/BUILD_STAGE.md` contains the first-builder / node-002+ / software-only decision tree.
- [ ] Stop rules between gates are explicit.
- [ ] RunPod is stated as **not required** for build.

## 3. Assembly

- [ ] `docs/build_assembly.md` lists **exact GPIO physical pins** (PIR 2/6/11, tamper 13/14).
- [ ] Wire colors, connector types, and standoff sizes specified.
- [ ] Power-on sequence has **expected voltages/current at each stage** (regulated 5 V USB before Pi).
- [ ] Common first-assembly mistakes table present.
- [ ] Enclosure fitment + cable management + antenna separation covered.
- [ ] Photo placeholders marked for the first builder to capture.

## 4. Flashing

- [ ] `docs/sd_flash_checklist.md` uses literal checkboxes.
- [ ] Exact `raspi-config nonint` commands included.
- [ ] RTL-SDR DVB blacklist + `rtl_test` verification included.
- [ ] Meshtastic region/channel/PSK config steps included.
- [ ] udev rule install + group membership verification included.

## 5. Failures

- [ ] `docs/known_first_build_failures.md` covers: power/boot, RTL/DVB, audio/PyAudio, Meshtastic serial/variant, GPIO, software/venv, thermal, enclosure.
- [ ] Every entry has symptom → root cause → exact fix command.

## 6. Gates G1–G5

- [ ] `validation/run_gate.py` runs each gate and writes `validation/reports/gate-gN.json`.
- [ ] `sentry-guard --probe` returns structured G1 PASS/FAIL with per-adapter remediation.
- [ ] `docs/gate_execution.md` has command + expected output + troubleshooting tree + plain pass criteria for each gate.
- [ ] G1 correctly FAILS off-Pi (sanity: prevents false "ready").

## 7. Procurement

- [ ] `configs/procurement_bom.json` has the approved 4-node production BOM with `component`, `purpose`, `unit_cost`, `quantity_per_node`, and `total_quantity` on every line.
- [ ] Critical risks called out: RTL-SDR Blog V4 RF limits, Waveshare LoRa HAT setup, counterfeit SD, regulated USB power only.
- [ ] Sourcing reliability (DigiKey/Amazon/AliExpress/vendor-direct) documented.
- [ ] "Order one node first" guidance present.

## 8. Deployment

- [ ] `docs/deployment_chain.md` labeled "paper concept only, hand emplacement required".
- [ ] Hand-deployment spacing (5–10 m) and 2–4 node mesh formation procedure present.

## 9. Defensive-only scope

- [ ] Every relevant file restates receive-only / no transmit / no engage.
- [ ] Export/ITAR review requirement stated where shipment/sale could occur.

## 10. Automated verification

- [ ] `pytest implementation/tests/ -q -k "not gpu"` passes.
- [ ] `python validation/build_readiness.py` prints `overall: PASS`.
- [ ] `python run_complete_audit.py` returns PASS.
- [ ] GitHub Actions CI green on `main`.
- [ ] Tag pushed (e.g. `v0.5.0-darkspace-integrated` or successor).

---

## Sign-off

| Field | Value |
|-------|-------|
| Package version | v0.5.0-darkspace-integrated |
| Reviewed by | __________________ |
| Date | __________________ |
| All boxes ticked? | ☐ Yes — handoff approved · ☐ No — not ready |

**Until all boxes are ticked, do not transfer this package as "build-ready".**
