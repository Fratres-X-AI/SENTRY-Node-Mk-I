# SENTRY Node Mk I — Assembly Procedure

**Type:** AN/GSQ-100(V)1 · **Audience:** technician who has never seen this device  
**Time:** ~90 min first node · **Mode:** Defensive-only

> Follow steps in order. Do not power the Pi until **Step 6** confirms 5.0 V at the buck output.
> Photo placeholders are marked `[PHOTO: ...]` — capture these on your first build for the next builder.

---

## 0. Tools and consumables

| Tool | Use |
|------|-----|
| Phillips #1 screwdriver | Enclosure, bracket |
| Small flat screwdriver | Buck trim pot (if adjustable) |
| Digital multimeter | **Mandatory** — voltage checks |
| Wire strippers / crimper | Dupont + XT30 |
| Zip ties (100 mm) | Cable management |
| Heat-shrink + lighter/gun | Strain relief |
| Anti-static strap | Pi handling |

Consumables: Dupont jumper wires (F-F, F-M), 22 AWG silicone wire, XT30 pigtail, M3 standoffs (12 mm), desiccant pack.

---

## 1. Bench layout and static safety (5 min)

1. Ground yourself (anti-static strap to a grounded point).
2. Lay out parts on a non-conductive mat.
3. **Do not** insert the SD card or connect the LiPo yet.

`[PHOTO: full parts layout before assembly]`

---

## 2. Raspberry Pi Zero 2 W mounting (10 min)

1. Fit four **M3 × 12 mm standoffs** to the enclosure lid panel.
2. Seat the Pi Zero 2 W on the standoffs, USB ports facing the gland side.
3. Secure with M3 nuts. **Do not overtighten** — PCB cracks. Snug only.

`[PHOTO: Pi on standoffs, ports oriented to glands]`

---

## 3. GPIO wiring (15 min) — EXACT PINS

Pi Zero 2 W uses the standard 40-pin header. **Pin = physical pin number.**

| Signal | Wire color (recommended) | Pi physical pin | BCM/GPIO | Notes |
|--------|--------------------------|-----------------|----------|-------|
| PIR VCC | **Red** | Pin 2 (5V) | — | HC-SR501 needs 5 V |
| PIR GND | **Black** | Pin 6 (GND) | — | Common ground |
| PIR OUT | **Yellow** | Pin 11 | GPIO17 | 3.3 V logic out — safe for Pi |
| Tamper reed A | **Blue** | Pin 13 | GPIO27 | Internal pull-up, active-low |
| Tamper reed B | **Black** | Pin 14 (GND) | — | Reed closes to GND |

**Connector type:** female Dupont to the Pi header; HC-SR501 has a 3-pin male header.

> **Critical:** HC-SR501 `OUT` is 3.3 V — safe. **Never** wire 5 V to a GPIO input pin. Double-check Pin 11 vs Pin 12 (easy to miscount).

`[PHOTO: GPIO header with PIR (pins 2/6/11) and reed (pins 13/14)]`

---

## 4. Power subsystem (10 min)

1. Mount the **5 V 2.5 A buck converter** on the enclosure floor (double-sided foam tape or M2 screws).
2. Wire **LiPo XT30 → buck IN**:
   - LiPo **red (+)** → buck **VIN+** (through an inline fuse holder, 3 A recommended).
   - LiPo **black (−)** → buck **VIN−**.
3. **Do not connect buck OUT to the Pi yet.**

> The 2S LiPo is **7.4 V nominal (8.4 V full)**. Feeding 7.4 V directly to the Pi will destroy it. The buck MUST step it down to 5.0 V first.

`[PHOTO: LiPo -> fuse -> buck IN; buck OUT not yet connected]`

---

## 5. USB tree (15 min)

Connect to the **powered 4-port USB OTG hub**:

| Hub port | Device | Connector |
|----------|--------|-----------|
| 1 | RTL-SDR Blog V3 (TCXO) | USB-A male |
| 2 | USB MEMS microphone | USB-A male |
| 3 | Meshtastic T-Beam (SX1262) | USB-C or micro (board-dependent) |
| 4 | Spare / debug | — |

Hub uplink (micro-USB) → Pi Zero 2 W **data** port (the inner micro-USB labeled `USB`, **not** `PWR`).

> The Pi Zero 2 W has two micro-USB ports. The **outer** one is power (`PWR`); the **inner** one is data (`USB`). The hub uplink goes to the **inner** `USB` port.

`[PHOTO: USB hub populated; uplink to inner USB port]`

---

## 6. Power-on sequence (10 min) — VOLTAGE CHECKS MANDATORY

Perform with a multimeter. **Do not skip.**

| Stage | Action | Measure | Expected | If wrong |
|-------|--------|---------|----------|----------|
| 6.1 | Connect LiPo to buck IN | Buck **VIN** | 7.0–8.4 V | Check LiPo charge / fuse |
| 6.2 | Read buck OUT (Pi NOT connected) | Buck **VOUT** | **5.0 V ± 0.1 V** | Adjust trim pot to 5.0 V; if non-adjustable and out of spec, replace buck |
| 6.3 | Connect buck OUT → Pi PWR rail | Pi 5V test point | 4.9–5.1 V | Re-check wiring; insufficient = brownout |
| 6.4 | Insert flashed SD, apply power | Green ACT LED | Blinks within ~10 s | See `known_first_build_failures.md` → "No boot" |
| 6.5 | Idle current draw | Inline ammeter | ~0.3–0.6 A idle | >1.2 A sustained = short; disconnect |

**Expected total node power:** ~2–3.3 W average (datasheet §6). G5 confirms < 5 W.

`[PHOTO: multimeter reading 5.0 V at buck OUT]`

---

## 7. Antennas (10 min)

| Antenna | Route | Orientation |
|---------|-------|-------------|
| RTL-SDR telescopic | Through M16 gland | **Vertical**, tip ~2.2 m AGL |
| LoRa whip (868/915 MHz) | Separate gland | Vertical; keep **≥150 mm** from RTL antenna |
| MEMS mic | 150 mm gooseneck, foam wind muff | Pointing outward/down |

> Keep the LoRa and RTL antennas physically separated — co-location desensitizes the RTL sweep. **Never power the Meshtastic board without its antenna attached** (risk of RF stage damage).

`[PHOTO: both antennas through glands, separation visible]`

---

## 8. Enclosure fitment and cable management (10 min)

- Internal clear height is ~70 mm and the stack is ~70 mm — **0 mm margin** with the 165×135×85 mm box. If it does not close, use the **150×120×90 mm** box (datasheet §3.1).
- Place the **desiccant pack** in a free corner.
- Route the LiPo flat against the floor; **no wires across standoff tips** (puncture risk).
- Align the **tamper reed** with the lid magnet so closing the lid keeps the reed closed.
- Zip-tie USB cables to avoid strain on the Pi's inner micro-USB.
- Tighten cable glands until the cable cannot be pulled by hand. Do not crush coax.

`[PHOTO: closed-ready internal layout with desiccant and reed alignment]`

---

## 9. Pole mount (20 min)

1. U-bolt the enclosure to a **50 mm pole** at **2.0 m AGL** (sensor reference height).
2. Aim the **PIR 15° outward/down**.
3. Verify antennas remain vertical after clamping.
4. **Label** the enclosure with the node ID (`sentry-pi-zero-00X`) — must match the SD hostname and `/etc/sentry/node_config.json`.

`[PHOTO: pole-mounted node, PIR angle, labels]`

---

## 10. First software bring-up (10 min)

```bash
cd /opt/sentry-node-mk-i
sudo bash deploy/bootstrap_pi_zero.sh
sentry-guard --probe --node-config /etc/sentry/node_config.json
```

Proceed to **G1** in [`gate_execution.md`](gate_execution.md). Do not enable the systemd service until G1 passes.

---

## Common first-assembly mistakes (avoid these)

| Mistake | Consequence | Prevention |
|---------|-------------|------------|
| 7.4 V LiPo straight to Pi | Pi destroyed | Always verify **5.0 V at buck OUT** before connecting Pi (Step 6.2) |
| Hub uplink to PWR port | No USB devices enumerate | Use the **inner** `USB` micro port |
| 5 V on a GPIO input | GPIO/Pi damage | PIR OUT is 3.3 V; never route 5 V to pins 11/13 |
| Meshtastic powered without antenna | RF stage damage | Attach LoRa antenna **before** power |
| RTL and LoRa antennas touching | RF desense, G2 fails | Keep ≥150 mm apart |
| Overtightened Pi standoffs | Cracked PCB | Snug only |
| No desiccant / loose glands | Condensation, corrosion | Desiccant in; glands hand-tight+ |
| Cheap non-TCXO RTL clone | Spectrum drift, G2 fails | Use RTL-SDR Blog V3 **TCXO** only |

---

## Defensive-only note

This is a **passive sensor**. No assembly step adds transmit/jam/engage capability. The Meshtastic radio transmits **only low-power mesh alert text** — review local RF regulations before powering antennas in your jurisdiction.
