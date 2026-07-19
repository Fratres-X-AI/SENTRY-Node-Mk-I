# SENTRY System Datasheet

**Codename:** SENTRY · **Version:** 0.5.0-darkspace-integrated · **Date:** 10 June 2026
**Organization:** Fratres X AI
**Mode:** Defensive-only · Passive early warning · **Working specification on paper**

| Field | Value |
|-------|-------|
| **Type designation** | **AN/GSQ-100(V)1** |
| **Common name** | **SENTRY Node Mk I** |
| **Role descriptor** | Passive Multi-Sensor Early-Warning Node (PMSEWN) |
| **Class** | Unattended ground sensor (UGS) / perimeter warning |
| **Emit mode** | Receive-only — no EW transmit, no engage |
| **4-node kit** | **AN/GSQ-100A(V)1** — SENTRY Net (4-pack) |

> **Briefing line:** AN/GSQ-100(V)1 SENTRY — passive ground early-warning node; PIR + acoustic + RF receive fusion; LoRa mesh alert relay; **no emit, no engage**.

**Note:** NSN, LIN, and formal program-of-record numbers are assigned by cataloging authority at fielding — not by Fratres.

This document is the single reference for physical dimensions, parts, wiring, power, mesh layout, and every output the node produces. Code implements this spec; field validation is still required before operational use.

---

## 0. Variant map

| Variant | Hardware baseline | Name |
|---------|-------------------|------|
| **(V)1** | Pi Zero 2 W, RTL-SDR Blog V4, USB mini microphone, HC-SR501 PIR, Waveshare 915 MHz LoRa HAT / Meshtastic bridge | **SENTRY Mk I** (current) |
| **(V)2** | (V)1 + hardened enclosure / solar feed | **SENTRY Mk II** |
| **(V)3** | Acoustic + PIR only (no RTL-SDR) | **SENTRY-Lite** |

Optional mesh gateway split (future): **AN/GSC-10(V)1** — SENTRY Mesh Gateway.

---

## 1. What one node is

A **SENTRY node** is a pole-mounted, IP65-enclosed Raspberry Pi Zero 2 W that:

1. Listens (never transmits EW countermeasures)
2. Fuses PIR + acoustic + RF + optional visual motion
3. Scores threat as CLEAR / YELLOW / ORANGE / RED / HOLD
4. Logs tamper-evident audit chain (HMAC)
5. Relays ORANGE+ alerts over Meshtastic LoRa mesh as compact OMEN JSON

**One node guards ~120 m radius** (configurable). A **4-node mesh** covers a ~240 m × 180 m rectangle with overlap.

---

## 2. System block diagram

```mermaid
flowchart TB
    subgraph enclosure [Field Enclosure 165x135x85mm]
        Pi[Pi Zero 2 W]
        PIR[HC-SR501 PIR GPIO17]
        Tamper[Tamper switch GPIO21]
        Mic[USB MEMS mic]
        RTL[RTL-SDR Blog V4 USB]
        LoRa[Waveshare 915 MHz LoRa HAT]
    end

    PIR --> Pi
    Tamper --> Pi
    Mic --> Pi
    RTL --> Pi
    LoRa <--> Pi

    Pi --> Fusion[sensor_fusion]
    Fusion --> Score[threat_scorer]
    Score --> Guard[sentry_guardian]
    Guard --> Alert[alert_frame.v1]
    Guard --> Audit[audit_entry.v1 HMAC chain]
    Alert --> Mesh[omen_alert.v1 via Meshtastic]
    Guard --> PowerLog[power_metrics.v1]
```

---

## 3. Mechanical package

### 3.1 Enclosure (per node)

| Parameter | Value |
|-----------|-------|
| Style | IP65 ABS junction box (Hammond 1591XX-class or equivalent) |
| External (L × W × H) | **165 × 135 × 85 mm** |
| Internal clear volume | **150 × 120 × 70 mm** |
| Mass (empty) | ~0.45 kg |
| Mount | U-bolt to **50 mm pole**, sensor head **2.0 m AGL** |
| Cable glands | 2× M16 bottom (USB pigtails, power) |
| Vent | Desiccant pack; no free breathing holes |

### 3.2 Internal stack-up (top → bottom, mm from enclosure floor)

| Layer | Component | Footprint (L×W mm) | Height mm |
|-------|-----------|------------------|-----------|
| 1 | RTL-SDR Blog V4 + antenna | 95 × 25 | 15 |
| 2 | Pi Zero 2 W on standoffs | 65 × 30 | 5 (board) + 12 standoff |
| 3 | Waveshare LoRa HAT / Meshtastic serial bridge | 65 × 30 | 20 |
| 4 | Anker PowerCore 10,000 mAh USB pack | 100 × 60 | 22 |
| 5 | Powered USB OTG hub | 80 × 45 | 15 |

**Total stacked height:** ~70 mm — fits internal clear height with tight margin (use a slimmer USB power bank or taller box if needed; **150×120×90 mm** box recommended for production).

### 3.3 External sensors (outside box)

| Sensor | Mount | Height AGL |
|--------|-------|------------|
| PIR (HC-SR501) | Bracket under enclosure lip, downward/ outward 15° | 2.0 m |
| USB MEMS mic | Foam wind muff, 150 mm arm from pole | 2.0 m |
| RTL antenna | Through gland, vertical polarisation | 2.2 m tip |
| LoRa antenna | 868/915 MHz whip, 200 mm | 2.3 m tip |

---

## 4. Bill of materials (one node)

| # | Part | Example SKU / class | Qty | Unit mass | Interface | Est. cost |
|---|------|---------------------|-----|-----------|-----------|-----------|
| 1 | Raspberry Pi Zero 2 W | SC0510 | 1 | 12 g | — | $15 |
| 2 | MicroSD 32 GB A2 | SanDisk Ultra | 1 | 0.5 g | SDIO | $8 |
| 3 | RTL-SDR Blog V4 Dongle | RTL2832U + R828D class | 1 | 25 g | USB | $35 |
| 4 | USB Mini Microphone | Generic USB audio | 1 | 15 g | USB | $8 |
| 5 | HC-SR501 PIR | Standard module | 1 | 20 g | GPIO 3.3 V | $2 |
| 6 | Waveshare LoRa HAT (915MHz) | Meshtastic OMEN relay module | 1 | 30 g | USB/serial | $22 |
| 7 | Tamper micro-switches & wires | Case switch loop | 1 set | 5 g | GPIO | $5 |
| 8 | Anker PowerCore 10000mAh Battery | Regulated USB power bank | 1 | 180 g | USB power | $26 |
| 9 | Micro-USB OTG Hub (4-Port) | Powered USB hub | 1 | 30 g | USB | $9 |
| 10 | IP67 Rugged Enclosure | Weatherproof case | 1 | 450 g | — | $25 |
| 11 | High-Gain 915MHz SMA Antenna | LoRa mesh antenna | 1 | 25 g | SMA | $14 |
| 12 | Cables & Mounting Hardware | USB lines, standoffs, zip-ties, thermal tape | 1 set | 50 g | — | $15 |
| 13 | Solar Panel Trickle Charger | Optional field endurance assist | 1 | 250 g | USB/5 V | $30 |

**Per-node electronics BOM:** ~\$216 (excl. pole, excl. labour)
**4-node site electronics:** ~\$864

---

## 5. Electrical & GPIO wiring

### 5.1 Power rail

| Rail | Source | Consumers | Peak A |
|------|--------|-----------|--------|
| 3.7 V nominal internal | USB power bank cells | Regulated pack input | 1.2 A |
| 5.0 V | USB power bank output | Pi, USB hub, RTL, mic, LoRa | **0.85 A peak** |
| 3.3 V | Pi GPIO | PIR, tamper switch (via Pi only) | 0.05 A |

### 5.2 GPIO (BCM numbering)

| Signal | GPIO | Direction | Pull | Notes |
|--------|------|-----------|------|-------|
| PIR OUT | **17** | IN | Down | HIGH = motion |
| Tamper switch | **21** | IN | Up | Pin 40 to Pin 39 GND; HIGH = enclosure opened |
| — | 22 | — | — | Reserved (status LED future) |

### 5.3 USB topology

```
Pi Zero 2 W (micro-USB OTG)
  └── Powered USB hub
        ├── RTL-SDR Blog V4
        ├── USB mini microphone
        └── Waveshare LoRa HAT / Meshtastic bridge
```

---

## 6. Power budget (real numbers)

### 6.1 Component draw (measured / datasheet typical)

| State | Pi Zero 2 W | RTL sweep | Acoustic FFT | LoRa TX | **Total** |
|-------|-------------|-----------|--------------|---------|-----------|
| Sleep window | 1.0 W | off | off | off | **1.0 W** |
| Active window | 2.5 W | +0.55 W | +0.25 W | off | **3.3 W** |
| Active + mesh alert | 2.5 W | +0.55 W | +0.25 W | +0.35 W | **3.65 W** |

### 6.2 Duty cycle (default config)

| Parameter | Value |
|-----------|-------|
| Active window | **4 s** (RF + acoustic + visual) |
| Sleep window | **6 s** (PIR + tamper only) |
| Duty factor active | 40 % |

**Average power (steady state):**

```
P_avg = 0.40 × 3.3 W + 0.60 × 1.0 W = 1.32 + 0.60 = 1.92 W
```

With occasional mesh TX (5 % of active frames): **~2.0 W average** — under **5 W target**.

### 6.3 Battery runtime (37 Wh pack example)

```
37 Wh / 2.0 W ≈ 18.5 h continuous
```

With 10 W solar panel (6 h effective sun): indefinite daytime + overnight buffer — **paper design only; measure on bench**.

### 6.4 Worst-case power with DARKSPACE passive tasks

This is the no-duty-cycle failure case: CPU saturated, RTL-SDR running continuously, Meshtastic transmitting at maximum power, and SQLite/psutil background tasks enabled.

| Component | Conservative draw |
|-----------|-------------------|
| Pi Zero 2 W at 100 % CPU | 2.5 W |
| RTL-SDR continuous sweep | +0.55 W |
| USB MEMS acoustic FFT | +0.25 W |
| SX1262 LoRa TX at max power | +1.0 W |
| DARKSPACE psutil + SQLite tasks | +0.15 W |
| **Worst-case total** | **4.45 W** |

Battery capacity: `10,000 mAh × 3.7 V internal nominal ≈ 37 Wh` before USB conversion losses.

```
37 Wh / 4.45 W = 8.3 h worst-case runtime
```

The default duty cycle remains mandatory. The software target is <60 % idle RAM on the Pi Zero 2 W and `MemoryMax=400M` under systemd.

### 6.5 Storage lifespan during ORANGE alerts

Assumptions: live ingest at 0.5 Hz, ORANGE state active 10 % of the hour, one SQLite event per frame, and HMAC JSONL flush for critical alerts.

```
0.5 frames/s × 3600 s/h × 0.10 × 2 writes = 360 critical writes/h
360 writes/h × 500 bytes ≈ 180 KB/h
180 KB/h × 24 × 180 days ≈ 760 MB over six months
```

A genuine 32 GB A2 micro-SD card with multi-TB write endurance is acceptable for six months at this alert rate. SQLite WAL checkpointing and bounded row retention reduce write amplification; sustained ORANGE duty above 10 % should use a high-endurance card.

### 6.6 SITE-ALPHA mesh link budget

The site rectangle is 240 m × 180 m, so the corner-to-corner diagonal is 300 m.

Using free-space path loss at 915 MHz:

```
FSPL = 20log10(300 m) + 20log10(915 MHz) - 27.55 = 81.2 dB
Rx = 22 dBm TX + 2 dBi TX + 2 dBi RX - 81.2 dB = -55.2 dBm
```

With 15-25 dB loss for trees, wet foliage, or light wall penetration, received power is approximately -70 to -80 dBm. SX1262 LoRa sensitivity at conservative spreading factors is roughly -125 to -130 dBm, leaving more than 45 dB of link margin at the longest site path. Field G4 still must verify this with installed antennas and local regulatory power settings.

---

## 7. RF & acoustic detection (paper performance)

### 7.1 RF — 2.4 GHz (RTL-SDR Blog V4, bench-proven hardware path required)

| Parameter | Value |
|-----------|-------|
| Sweep | 2400–2500 MHz, 200 kHz bins, 2 s integration |
| Burst threshold | +10 dB above rolling baseline |
| Jamming heuristic | Wideband uplift >12 dB, low bin spread |
| Max RTL2832/R828D tune | ~1766 MHz upper — **2.4 GHz requires upconverter, harmonic method, or SDR rated ≥2.5 GHz** |

**Critical honesty:** RTL-SDR Blog V4 still uses an RTL2832-class receiver path and is not a native 2.4 GHz/5.8 GHz instrument. Treat 2.4 GHz as a planned/bench-proven path and verify your specific dongle, antenna, and any conversion method before field claims. Code sweeps 2400–2500 MHz per config; bench prove before operational use.

### 7.2 RF — 5.8 GHz

| Status | **Not available on RTL2832** |
| v0.5.0 behaviour | Synthetic fallback only |
| Future | Separate 5.8 GHz receiver module |

### 7.3 Friis link budget example (2.45 GHz planning)

| Parameter | Value |
|-----------|-------|
| Emitter ERP | 20 dBm (100 mW) |
| Distance | 300 m |
| Rx antenna | 2 dBi whip |
| **Estimated Rx (free space)** | **≈ −72 dBm** |

Use `RfSensor.friis_note()` in code — planning only, not detection probability.

### 7.4 Acoustic — 100–500 Hz

| Parameter | Value |
|-----------|-------|
| Sample rate | 16 kHz |
| Frame | 4096 samples (256 ms) |
| Method | Hanning window → FFT → `find_peaks` in band |
| Target signature | Small UAS propeller fundamental + harmonics |
| Mic sensitivity | −42 dB typical MEMS |

**Field risk:** Wind and vehicle traffic produce false peaks — expect tuning per site.

---

## 8. Four-node mesh layout (SITE-ALPHA-001)

Reference deployment: [`configs/deployment_site_alpha.json`](../configs/deployment_site_alpha.json)

```
                    NE (node-001) ───────────── NW (node-002)
                         │    \               /    │
                         │     \   relay     /     │
                         │      (node-004)          │
                         │           │              │
                    240 m │           │              │ 240 m
                         │           │              │
                         │      gate (node-003)     │
                         └─────────── south ────────┘
                              180 m depth
```

| Node | Role | Post | Lat/Lon (example) | Guardian radius |
|------|------|------|-------------------|-----------------|
| sentry-pi-zero-001 | NE corner | Post A | 51.50820, −0.12650 | 120 m |
| sentry-pi-zero-002 | NW corner | Post B | 51.50820, −0.12910 | 120 m |
| sentry-pi-zero-003 | Gate | Post C | 51.50680, −0.12780 | 120 m |
| sentry-pi-zero-004 | Relay | Mast | 51.50750, −0.12780 | 120 m |

**Inter-node spacing:** 240 m (long side), 180 m (short side)
**Overlap:** ~40 m between adjacent 120 m circles — dual-trigger possible near boundaries

### Meshtastic mesh

| Parameter | Value |
|-----------|-------|
| Radio | Waveshare 915 MHz LoRa HAT / Meshtastic-compatible bridge |
| Region example | EU868 / US915 (set per jurisdiction) |
| Channel | 1 (shared across site) |
| Payload | `omen_alert.v1` JSON, ≤200 bytes |
| Peers | All nodes hear all; spool if TX fails |

---

## 9. Outputs (every artefact the node produces)

| Output | Schema | Path (default) | When emitted |
|--------|--------|----------------|--------------|
| Sensor frame | `sensor_event.v1` | In-memory → alert embed | Every sample (0.5 Hz live) |
| Alert | `alert_frame.v1` | `sentry_live_alerts.jsonl` | Every sample after fusion |
| Audit entry | `audit_entry.v1` | `sentry_live_audit.jsonl` | boot, alert, tamper |
| Power sample | `power_metrics.v1` | `sentry_power.jsonl` | Every sample |
| Mesh alert | `omen_alert.v1` | Meshtastic OTA or spool | ORANGE, RED, HOLD |
| Defense audit | JSON report | `defense-readiness-sentry.json` | CI / manual audit run |

**Example payloads:** [`docs/examples/`](examples/)

### 9.1 Alert levels (operator-facing)

| Level | Threat score | Meaning | Mesh TX |
|-------|--------------|---------|---------|
| CLEAR | < 0.35 | Normal passive watch | No |
| YELLOW | 0.35–0.55 | Elevated activity | No |
| ORANGE | 0.55–0.75 | Early warning — investigate | **Yes** |
| RED | ≥ 0.75 | High confidence warning | **Yes** |
| HOLD | Jamming / tamper | Hold-safe — human decision | **Yes** |

### 9.2 Guardian states

| State | Meaning |
|-------|---------|
| `watch` | Baseline |
| `confirming` | Dwell timer (3 s default) before ORANGE/RED |
| `alerting` | Confirmed elevated |
| `cooldown` | 30 s suppression after escalation clears |
| `hold_safe` | Tamper or jamming HOLD |

---

## 10. Timing & latency (paper budget)

| Stage | Latency |
|-------|---------|
| Sample period (live) | 2.0 s (0.5 Hz) |
| RTL sweep (active window) | up to 12 s timeout, 2 s typical |
| Acoustic frame | 256 ms capture + ~50 ms FFT |
| Fusion + score | < 10 ms |
| Dwell confirm | 3 s before ORANGE/RED |
| Mesh TX | 0.5–2 s LoRa airtime |
| **End-to-end (detection → mesh)** | **4–18 s typical** |

---

## 11. Software map → hardware

| Spec section | Code module |
|--------------|-------------|
| RF 2.4/5.8 | `sensors/rf_sensor.py` |
| Acoustic 100–500 Hz | `sensors/acoustic_sensor.py` |
| Power metrics | `sensors/power_metrics.py` |
| GPIO PIR / tamper | `hardware/pir.py`, `hardware/tamper.py` |
| Guardian FSM | `guardian.py` |
| Live loop | `ingest.py`, `sentry-guard --live` |
| Mesh OMEN | `networking/meshtastic_handler.py` |
| Simulation fallback | `simulation/synthetic.py` |

---

## 12. Bench & acceptance (paper gates)

| Gate | Criterion | Tool |
|------|-----------|------|
| G0 | All pytest + audit PASS | `python run_complete_audit.py` |
| G1 | Probe shows RTL + mic + GPIO on Pi | `sentry-guard --probe` |
| G2 | 2.4 GHz burst from test emitter detected | Lab signal gen |
| G3 | 220 Hz tone → acoustic_propeller_peak | Speaker @ 5 m |
| G4 | 4-node mesh receives ORANGE within 5 s | Meshtastic app |
| G5 | 8 h soak, P_avg < 5 W, no thermal throttle | Power log analysis |

**Current status:** G0 pass on desktop simulation. **G1–G5 not executed.**

---

## 13. What this document is not

- Not a validated field performance guarantee
- Not export-cleared (see [`export_screening.md`](export_screening.md))
- Not a substitute for bench test with real emitters and noise

It **is** the complete on-paper system: dimensions, parts, wiring, power, layout, outputs, and acceptance gates — ready for procurement and bench build.
