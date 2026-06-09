# SENTRY Build Stage — Master Checklist

**Type:** AN/GSQ-100(V)1 · **SENTRY Node Mk I** · **Version:** 0.4.0-build  
**Date:** 7 June 2026 · **Mode:** Defensive-only

This is the gate between **“idea in repo”** and **“soldering parts.”** Everything below marked **SOFTWARE** can be done without a bench. Everything marked **PHYSICAL** needs parts in hand.

---

## Where you are right now

| Layer | Status |
|-------|--------|
| Simulation + guardian + audit | **DONE** (G0 pass) |
| Pi drivers + systemd + bootstrap | **DONE** (templates) |
| Datasheet + BOM + ICD + risks | **DONE** |
| Military designation | **DONE** (AN/GSQ-100(V)1) |
| GitHub CI | **DONE** (main branch) |
| Deployment chain (paper) | **DONE** (mechanical-only sim) |
| **Build pack (this doc + procurement + assembly)** | **IN PROGRESS → DONE today** |
| Bench validation G1–G5 | **NOT STARTED** (needs hardware) |

**BLUNT:** You can **procure and assemble today**. You cannot **claim field-validated EW** until G1–G5 pass on real hardware.

---

## Build stage definition (Fratres)

**Build stage =** frozen BOM, frozen configs, flashable Pi image procedure, assembly order, 4-node site manifest, software tag, CI green, procurement list — **zero ambiguity for whoever buys parts.**

**Not build stage:** shock tests, emitter lab, mesh soak in field, export counsel sign-off.

---

## SOFTWARE — do today (no RunPod, no parts)

| # | Task | Command / artifact | Status |
|---|------|-------------------|--------|
| S1 | Full test + audit | `python run_complete_audit.py` | Run before tag |
| S2 | Build readiness gate | `python validation/build_readiness.py` | Added today |
| S3 | 4-node configs | `configs/nodes/sentry-pi-zero-00X.json` | Added today |
| S4 | Frozen procurement BOM | `configs/procurement_bom.json` | Added today |
| S5 | Assembly procedure | `docs/build_assembly.md` | Added today |
| S6 | SD flash checklist | `docs/sd_flash_checklist.md` | Added today |
| S7 | Commit + push + CI green | `git push origin main` | Do after S1–S6 |
| S8 | Git tag | `v0.4.0-build` | After CI green |

### RunPod — do you need it?

**No — not for build stage.**

RunPod is only for **GPU Monte Carlo / melt reports** (already ran once on A100). Skip unless you want a fresh `gpu-stress-test.json` in the repo for HQ slides.

If you want that anyway: spin **A100 or any CUDA pod**, run `bash validation/runpod/run_melt_pod.sh` (~5 min). **Tell me when the pod is up** and I’ll drive it.

---

## PHYSICAL — after you order parts (not today in software)

| Gate | What | Parts needed | Est. time |
|------|------|--------------|-----------|
| **G1** | `sentry-guard --probe` all green on Pi | 1× full node BOM | 2 h assemble + flash |
| **G2** | 2.4 GHz test emitter → RF alert | Node + cheap 2.4 GHz source | 1 h |
| **G3** | 220 Hz speaker @ 5 m → acoustic peak | Node + speaker | 30 min |
| **G4** | 4-node mesh ORANGE < 5 s | 4× nodes + Meshtastic app | 4 h |
| **G5** | 8 h soak, P_avg < 5 W | 1× node + power meter optional | 8 h unattended |

### Order this (4-node site + spares)

See **`configs/procurement_bom.json`**. Round-number shopping:

| Category | Qty | ~Cost |
|----------|-----|-------|
| Full node kits | 4 | ~$864 |
| Spares kit | 1 | ~$120 |
| Poles + mounts | 4 | ~$120 |
| **Total first build** | — | **~$1,100** |

Recommended: order **1 node first** for G1–G3, then duplicate ×3 after probe pass.

---

## Day-one physical workflow (when box arrives)

```
1. Flash SD (docs/sd_flash_checklist.md)
2. Clone repo → bootstrap (docs/pi_deployment.md)
3. sentry-guard --probe          → G1
4. sentry-guard --live --duration 60
5. python run_complete_audit.py  → G0 on Pi
6. Lab emitter tests             → G2, G3
7. Deploy 4 corners              → G4
8. Overnight soak                → G5
```

---

## Known gaps (honest — do not hide at build)

| Gap | Impact at build | Fix |
|-----|-----------------|-----|
| 5.8 GHz RF | Synthetic only | Accept for Mk I or add downconverter later |
| Meshtastic RX | Spool placeholder | Alerts TX OK; peer RX manual via app |
| Export counsel | Not signed | Block **international** ship until cleared |
| Chain deployment | Paper sim only | Hand-emplace for Mk I |

---

## Done = build stage complete when

- [x] G0 software gate passes locally and on CI  
- [x] Procurement BOM frozen  
- [x] 4-node configs + site manifest frozen  
- [x] Assembly + flash docs written  
- [x] Tag `v0.4.0-build` pushed  
- [ ] G1–G5 (physical — your bench week)

**After tag:** open shopping cart, build node 001, run `--probe`.
