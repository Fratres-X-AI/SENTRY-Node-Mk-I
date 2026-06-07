# SENTRY Project Overview

**Codename:** SENTRY · **Version:** 0.3.0 · **Mode:** Defensive-only  
**Type designation:** **AN/GSQ-100(V)1** (SENTRY Node Mk I) · **PMSEWN** — Passive Multi-Sensor Early-Warning Node

SENTRY is a **4-node-capable** passive early-warning mesh built on Raspberry Pi Zero 2 W. Each pole-mounted node fuses motion, acoustic (100–500 Hz), RF (2.4 GHz passive sweep), and optional visual motion into explainable alerts relayed over Meshtastic LoRa.

## On-paper system (complete spec)

The project is designed to be a **working thing on paper** before bench validation:

| What | Where |
|------|-------|
| Enclosure 165×135×85 mm, 2.0 m AGL mount | [`system_datasheet.md`](system_datasheet.md) §3 |
| Full BOM with masses and ~$216/node | [`bom_dimensions.md`](bom_dimensions.md) |
| GPIO 17 PIR, GPIO 27 tamper, USB tree | [`system_datasheet.md`](system_datasheet.md) §5 |
| Power: ~2.0 W avg, 18 h on 37 Wh | [`system_datasheet.md`](system_datasheet.md) §6 |
| 240×180 m site, 4 nodes, 120 m radius each | [`deployment_site_alpha.json`](../configs/deployment_site_alpha.json) |
| All JSON outputs + examples | [`outputs_icd.md`](outputs_icd.md), [`examples/`](examples/) |

## Pipeline

Fusion → scoring (CLEAR/YELLOW/ORANGE/RED/HOLD) → guardian FSM → audit chain + mesh OMEN relay. **No engagement logic.**

## Validation status

- **G0 (software):** pytest + audit PASS on desktop simulation  
- **G1–G5 (hardware):** Not executed — see datasheet §12

## Related

- Install: [`pi_deployment.md`](pi_deployment.md)  
- Risks: [`risk_register.md`](risk_register.md)  
- Export: [`export_screening.md`](export_screening.md)
