# SENTRY Build Stage — Single Source of Truth

**Type:** AN/GSQ-100(V)1 · **SENTRY Node Mk I** · **Version:** v0.5.0-darkspace-integrated
**Mode:** Defensive-only · Receive-only

> This document governs the **entire build process**. If any other document conflicts with this one, **this document wins**. Read [`../HANDOFF_README.md`](../HANDOFF_README.md) first.

---

## 0. Who are you? (decision tree)

```
START
  |
  +-- Are you building the FIRST node ever (node 001)?
  |     |
  |     YES -> Go to PATH A (First Builder). Order 1 node + spares only.
  |     |       Prove G1-G5 before buying more hardware.
  |     |
  |     NO  -> Are you building node 002, 003, or 004 (G1 already passed on 001)?
  |             |
  |             YES -> Go to PATH B (Replicate Node). Skip lab gates G2/G3;
  |                     run G1 per node, then site-level G4 once all nodes are up.
  |
  +-- Are you ONLY changing software (no hardware)?
        |
        YES -> Go to PATH C (Software Only). Run build_readiness + CI. No parts needed.
```

---

## PATH A — First Builder (node 001)

| # | Action | Command / Doc | Gate |
|---|--------|---------------|------|
| A1 | Read handoff + scope | [`../HANDOFF_README.md`](../HANDOFF_README.md) | — |
| A2 | Order **1 node + spares** | [`../configs/procurement_bom.json`](../configs/procurement_bom.json) | — |
| A3 | Flash SD card | [`sd_flash_checklist.md`](sd_flash_checklist.md) | — |
| A4 | Assemble node | [`build_assembly.md`](build_assembly.md) | — |
| A5 | Provision software | `sudo bash deploy/bootstrap_pi_zero.sh` | — |
| A6 | **G1 hardware probe** | `sentry-guard --probe --node-config /etc/sentry/node_config.json` | **G1** |
| A7 | RF burst test | `python validation/run_gate.py --gate G2` + emitter | **G2** |
| A8 | Acoustic tone test | `python validation/run_gate.py --gate G3` + speaker | **G3** |
| A9 | (Needs 2nd node) mesh relay | `python validation/run_gate.py --gate G4` | **G4** |
| A10 | 8 h soak / power | `python validation/run_gate.py --gate G5 --soak-minutes 480` | **G5** |
| A11 | Only after G1–G3 pass: order 3 more nodes | — | — |

**STOP RULE:** Do not advance a gate until the previous one is `pass=true` (or manually confirmed for G2–G5). See [`gate_execution.md`](gate_execution.md).

---

## PATH B — Replicate Node (002+)

Pre-condition: G1, G2, G3 already passed on node 001.

| # | Action | Command / Doc |
|---|--------|---------------|
| B1 | Flash SD with node-specific hostname | [`sd_flash_checklist.md`](sd_flash_checklist.md) |
| B2 | Assemble (identical to 001) | [`build_assembly.md`](build_assembly.md) |
| B3 | Copy the matching node config | `sudo cp configs/nodes/sentry-pi-zero-00X.json /etc/sentry/node_config.json` |
| B4 | **G1 per node** | `sentry-guard --probe --node-config /etc/sentry/node_config.json` |
| B5 | After all nodes up: **site G4** | `python validation/run_gate.py --gate G4` |
| B6 | Deploy per site manifest | [`../configs/deployment_site_alpha.json`](../configs/deployment_site_alpha.json) |

You may skip re-running G2/G3 per node **only if** the BOM and assembly are identical to the validated node 001. Document any deviation.

---

## PATH C — Software Only (no parts)

| # | Action | Command |
|---|--------|---------|
| C1 | Install dev deps | `pip install -e "implementation[dev]"` |
| C2 | Run tests | `pytest implementation/tests/ -q -k "not gpu"` |
| C3 | Software build gate | `python validation/build_readiness.py` |
| C4 | Full audit | `python run_complete_audit.py` |
| C5 | Push + confirm CI green | `git push origin main` |

**RunPod:** Not required for any build path. RunPod is only for optional GPU Monte Carlo / stress reports (`validation/runpod/run_melt_pod.sh`). If you spin up a pod, tell the author/operator; otherwise skip it.

---

## Build stage definition (Fratres)

**Build stage is COMPLETE (software) when:**

- [x] G0/software gate passes locally and in CI (`validation/build_readiness.py`)
- [x] Procurement BOM frozen as approved 4-node production BOM
- [x] 4-node configs + site manifest frozen
- [x] Assembly, flash, gate, and failure docs written for a non-author
- [ ] Release tag pushed after CI green

**Build stage is COMPLETE (physical) when:**

- [ ] G1 probe pass on node 001
- [ ] G2 RF burst confirmed
- [ ] G3 acoustic peak confirmed
- [ ] G4 mesh ORANGE relay < 5 s (≥2 nodes)
- [ ] G5 8 h soak, mean power < 5 W, no throttle

---

## Acceptance gates (summary — full detail in `gate_execution.md`)

| Gate | What it proves | Needs | Pass criteria |
|------|----------------|-------|---------------|
| **G1** | Hardware enumerates (BIT) | 1 node | All required adapters available on Pi |
| **G2** | RF channel works | 2.4 GHz emitter | `rf_burst_2g4` appears when emitter on |
| **G3** | Acoustic channel works | 220 Hz speaker | `acoustic_propeller_peak` appears with tone |
| **G4** | Mesh relays alerts | ≥2 nodes | Peer receives ORANGE OMEN < 5 s |
| **G5** | Power/thermal budget | 1 node, 8 h | Mean < 5 W, no thermal throttle |

---

## Known limitations carried into build (do not hide)

| Limitation | Action for builder |
|------------|--------------------|
| 5.8 GHz synthetic only | Accept for Mk I; never claim 5.8 GHz detection |
| Meshtastic RX manual | Confirm inbound via Meshtastic phone app |
| Chain deploy paper-only | Hand-emplace nodes (see `deployment_chain.md`) |
| Export not cleared | Block international shipment until counsel sign-off |
