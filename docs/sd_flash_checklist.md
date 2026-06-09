# SENTRY SD Card Flash Checklist

**Target:** Raspberry Pi Zero 2 W · **Image:** Raspberry Pi OS Lite (64-bit, Bookworm class)  
**Build tag:** `v0.4.0-build`

## Before flash

- [ ] MicroSD 32 GB A2 (SanDisk Ultra or equivalent)
- [ ] USB micro-B data cable (not charge-only)
- [ ] Pi Imager installed on workstation

## Flash steps

1. Insert SD into reader.
2. **Raspberry Pi Imager** → Choose device **Pi Zero 2 W**.
3. Choose OS: **Raspberry Pi OS Lite (64-bit)**.
4. Gear icon → set:
   - Hostname: `sentry-pi-zero-XXX` (match node config)
   - Enable SSH (password or key)
   - User: `pi` (or dedicated `sentry`)
   - Locale / timezone
   - **Wi‑Fi** if bench testing without Ethernet (optional)
5. Write → verify.
6. Insert SD into Pi Zero 2 W; power via **5 V 2.5 A** supply.

## First boot (bench)

```bash
ssh pi@sentry-pi-zero-001.local
sudo apt update && sudo apt upgrade -y
git clone https://github.com/Fratres-X-AI/SENTRY-Node-Mk-I.git /opt/sentry-node-mk-i
cd /opt/sentry-node-mk-i
sudo bash deploy/bootstrap_pi_zero.sh
```

Copy node-specific config:

```bash
sudo cp configs/nodes/sentry-pi-zero-001.json /etc/sentry/node_config.json
sudo systemctl enable --now sentry-guardian   # after reviewing deploy/sentry-guardian.service
/opt/sentry-node-mk-i/.venv/bin/sentry-guard --probe
```

## Pre-power hardware check (no SD yet)

- [ ] Pi Zero 2 W seated on standoffs, no shorts
- [ ] USB hub powered; Pi fed from buck 5 V (not hub back-power only)
- [ ] PIR on GPIO 17, tamper reed GPIO 27
- [ ] RTL-SDR on USB — antenna **not** touching metal enclosure
- [ ] Meshtastic on `/dev/ttyACM0` (check `ls /dev/ttyACM*` after boot)
- [ ] LiPo polarity correct (XT30); use fused feed if bench testing battery

## Pass criteria (G1)

`sentry-guard --probe` shows **≥4 adapters available** on Pi with hardware attached (PIR, acoustic, RF, tamper, meshtastic — visual optional).

## Fail actions

| Symptom | Check |
|---------|--------|
| RTL not found | `rtl_test`, blacklist dvb (`deploy/bootstrap_pi_zero.sh`) |
| No `/dev/ttyACM0` | Meshtastic USB cable, udev rules |
| PyAudio fail | `portaudio19-dev`, replug mic |
| GPIO permission | User in `gpio` group, reboot |
