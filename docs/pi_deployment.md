# SENTRY — Raspberry Pi Zero 2 W Deployment

**Codename:** SENTRY · **Version:** 0.3.0 · **Mode:** Defensive-only  
**Type designation:** **AN/GSQ-100(V)1** · SENTRY Node Mk I · PMSEWN (receive-only)

Full BOM, bootstrap, systemd, and test commands for field bench. See also [`risk_register.md`](risk_register.md) and [`export_screening.md`](export_screening.md).

---

## 1. Bill of Materials (cheap / COTS)

| Qty | Item | Interface | Notes |
|-----|------|-----------|-------|
| 1 | Raspberry Pi Zero 2 W | — | 512 MB RAM — duty cycle mandatory |
| 1 | MicroSD 32 GB A2 | — | |
| 1 | 5 V 2.5 A PSU | USB micro-B | |
| 1 | RTL-SDR Blog V3 | USB | **2.4 GHz only** (RTL2832 ~1.76 GHz max) |
| 1 | USB MEMS mic | ALSA | 100–500 Hz propeller band |
| 1 | HC-SR501 PIR | GPIO 17 | |
| 1 | Meshtastic (SX1262 LoRa) | `/dev/ttyACM0` | 2–4 node mesh |
| 1 | NC tamper reed | GPIO 27 | Active-low |
| 1 | Basic LiPo + boost (optional) | — | Size for <5 W avg budget |

**5.8 GHz gap:** RTL-SDR V3 **cannot** tune 5800–5900 MHz. Code alternates 2g4 (hardware) and 5g8 (**synthetic fallback**). Do not claim 5.8 GHz detection without new RF front-end.

---

## 2. Bootstrap (one command)

```bash
git clone https://github.com/Fratres-X-AI/SENTRY-Node-Mk-I.git /opt/sentry-node-mk-i
cd /opt/sentry-node-mk-i
chmod +x deploy/bootstrap_pi_zero.sh
./deploy/bootstrap_pi_zero.sh
```

Installs: `rtl-sdr`, `portaudio`, Python venv, `sentry[hardware,dev,pi]`, udev rules.

---

## 3. raspi-config / OS

```bash
# Raspberry Pi OS Lite 64-bit Bookworm
sudo raspi-config noninteractive <<EOF
do_hostname sentry-node
do_memory_split 16
EOF
echo "gpu_mem=16" | sudo tee -a /boot/firmware/config.txt

# RTL-SDR: blacklist DVB driver
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/rtl-sdr-blacklist.conf
sudo modprobe -r dvb_usb_rtl28xxu 2>/dev/null || true
```

---

## 4. udev

```bash
sudo cp deploy/99-sentry.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
rtl_test -t
rtl_power -f 2400M:2500M:200k -i 2 -1
```

---

## 5. Configuration

```bash
sudo mkdir -p /etc/sentry /var/lib/sentry
sudo cp configs/sentry_node_config.json /etc/sentry/node_config.json
sudo cp configs/sentry_mission_profile.json /etc/sentry/mission_profile.json
export SENTRY_AUDIT_HMAC_KEY="$(openssl rand -hex 32)"
# Production: set tamper_response.dry_run=false only after counsel review
```

---

## 6. Test commands (on Pi bench)

```bash
source /opt/sentry-node-mk-i/.venv/bin/activate

# Adapter probe (reports real vs fallback)
sentry-guard --probe --node-config /etc/sentry/node_config.json

# Jamming scenario (simulation)
sentry-sim --scenario jamming

# Live ingest with hardware + fallback (30 s bench)
sentry-guard --live --duration 30 --rate-hz 0.5 \
  --node-config /etc/sentry/node_config.json

# Failure modes + power metrics
sentry-guard --failure-modes

# Full audit (scenarios + probe + live smoke + power)
python /opt/sentry-node-mk-i/run_complete_audit.py
```

---

## 7. systemd continuous service

```bash
# Set SENTRY_AUDIT_HMAC_KEY in unit or /etc/sentry/environment
sudo cp deploy/sentry-guardian.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sentry-guardian
journalctl -u sentry-guardian -f -t SENTRY
```

`MemoryMax=400M` for Zero 2 W. ExecStart runs `sentry-guard --live` with duty-cycled sensors.

---

## 8. Power profiling

Logged to `validation/reports/sentry_power.jsonl` (config: `power.log_path`):

- `psutil` CPU/RAM
- `vcgencmd` temp/throttle on Pi
- Datasheet-based watt estimate (idle 1.0 W, active 2.5 W, +RTL +0.55 W, +acoustic +0.25 W)
- Target: **< 5 W average** with 4 s active / 6 s sleep duty cycle

---

## 9. Meshtastic mesh (2–4 nodes)

Configure peers in `hardware.meshtastic.peers`. ORANGE/RED/HOLD alerts emit `omen_alert.v1` JSON. Spool fallback: `/var/lib/sentry/meshtastic_spool.jsonl`.

**Gap:** RX is spool-placeholder — no live mesh RX callback wired yet.

---

## 10. Tamper response

GPIO tamper → `HOLD` alert → HMAC audit `tamper_wipe` event. Default **`dry_run: true`** — set `tamper_response.dry_run: false` in production to wipe env keys and spool files.

---

## 11. Known limitations (blunt)

- Simulation ≠ field EW; bench 1–2 nodes before any operational claim
- 5.8 GHz is synthetic on RTL-SDR V3
- Acoustic wind/traffic false positives likely — untuned in field
- Meshtastic throughput/jamming not characterized
- Friis helper is planning-only — not wired to live detection range
