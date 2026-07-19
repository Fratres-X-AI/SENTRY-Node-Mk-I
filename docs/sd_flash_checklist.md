# SENTRY SD Card Flash & Provision — Literal Checklist

**Target:** Raspberry Pi Zero 2 W · **OS:** Raspberry Pi OS Lite (64-bit, Bookworm)  
**Type:** AN/GSQ-100(V)1 · **Build tag:** v0.5.0-darkspace-integrated

> Tick every box. If a verification command does not produce the expected output, stop and see
> [`known_first_build_failures.md`](known_first_build_failures.md).

---

## A. Before flashing

- [ ] MicroSD 32 GB A2 (SanDisk Ultra or equivalent) inserted in workstation reader
- [ ] USB micro-B **data** cable available (not charge-only)
- [ ] Raspberry Pi Imager installed ([raspberrypi.com/software](https://www.raspberrypi.com/software/))
- [ ] Decide node ID now: `sentry-pi-zero-001` (must match config + label)

---

## B. Flash the OS

- [ ] Open Raspberry Pi Imager
- [ ] **Choose Device:** Raspberry Pi Zero 2 W
- [ ] **Choose OS:** Raspberry Pi OS Lite (64-bit)
- [ ] **Choose Storage:** the microSD (verify the device letter — wrong target wipes other drives)
- [ ] Click the **gear / EDIT SETTINGS** and set:
  - [ ] Hostname: `sentry-pi-zero-001`
  - [ ] Enable SSH (prefer **public-key**; password acceptable for bench)
  - [ ] Username: `pi` (or dedicated `sentry`)
  - [ ] Wi-Fi SSID + password (bench only; production may be wired/headless)
  - [ ] Locale / timezone
- [ ] **WRITE** and wait for verify to complete
- [ ] Reinsert the SD to confirm the workstation reads the boot partition

---

## C. First boot

- [ ] Insert SD into Pi; power via **5 V 2.5 A** (confirmed in assembly Step 6)
- [ ] Wait ~60 s for first-boot expansion
- [ ] SSH in:

```bash
ssh pi@sentry-pi-zero-001.local
```

- [ ] Update base OS:

```bash
sudo apt update && sudo apt full-upgrade -y
```

---

## D. Headless config (raspi-config)

- [ ] Run:

```bash
sudo raspi-config nonint do_ssh 0          # ensure SSH enabled
sudo raspi-config nonint do_spi 1          # SPI off (unused)
sudo raspi-config nonint do_i2c 0          # I2C on (optional sensors)
sudo raspi-config nonint do_serial_hw 0    # serial HW on for UART peripherals
sudo raspi-config nonint do_serial_cons 1  # serial login shell OFF (frees UART)
```

- [ ] Set GPU mem low (headless):

```bash
sudo raspi-config nonint do_memory_split 16
```

- [ ] Reboot:

```bash
sudo reboot
```

---

## E. Clone repo and provision

- [ ] Clone the repository:

```bash
git clone https://github.com/Fratres-X-AI/SENTRY-Node-Mk-I.git /opt/sentry-node-mk-i
cd /opt/sentry-node-mk-i
```

- [ ] Run the bootstrap (installs apt deps, venv, udev, config):

```bash
sudo bash deploy/bootstrap_pi_zero.sh
```

- [ ] Copy the node-specific config:

```bash
sudo cp configs/nodes/sentry-pi-zero-001.json /etc/sentry/node_config.json
sudo cp configs/sentry_mission_profile.json /etc/sentry/mission_profile.json
```

---

## F. RTL-SDR setup and verification

- [ ] Confirm DVB driver blacklisted (bootstrap does this; verify):

```bash
cat /etc/modprobe.d/rtl-sdr-blacklist.conf
# expect: blacklist dvb_usb_rtl28xxu
```

- [ ] Reboot if you just added the blacklist:

```bash
sudo reboot
```

- [ ] Verify the dongle:

```bash
rtl_test -t
```

- [ ] **Expected:** `Found 1 device(s):  0:  Realtek, RTL2838UHIDIR` and a tuner line. If "usb_claim_interface error -6", the DVB driver is still loaded — see failures doc.

---

## G. USB audio (microphone) verification

- [ ] List capture devices:

```bash
arecord -l
```

- [ ] **Expected:** a `card X: ... [USB Audio]` entry.
- [ ] Quick capture test (2 s):

```bash
arecord -D plughw:1,0 -d 2 -f S16_LE -r 16000 /tmp/test.wav && echo OK
```

---

## H. Meshtastic configuration (manual)

> Inbound mesh RX is **manual / app-based** for Mk I. These steps register the device and channel; confirm receive via the phone app.

- [ ] Confirm serial device:

```bash
ls -l /dev/ttyACM* /dev/meshtastic
```

- [ ] Install Meshtastic CLI (optional, for headless config):

```bash
/opt/sentry-node-mk-i/.venv/bin/pip install meshtastic
```

- [ ] Set region and channel (example — set YOUR legal region):

```bash
meshtastic --port /dev/ttyACM0 --set lora.region EU_868   # or US, etc.
meshtastic --port /dev/ttyACM0 --ch-index 1 --ch-set name SENTRY --ch-set psk random
```

- [ ] Verify info:

```bash
meshtastic --port /dev/ttyACM0 --info
```

- [ ] On a second node or phone app, confirm the `SENTRY` channel is visible.

---

## I. udev rules verification

- [ ] Rules installed:

```bash
ls -l /etc/udev/rules.d/99-sentry.rules
```

- [ ] Reload if you just copied them:

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```

- [ ] Confirm group membership (RTL + serial access):

```bash
groups
# expect: ... sentry ... dialout ... plugdev ...
```

---

## J. G1 gate (final check of this checklist)

- [ ] Run the probe:

```bash
sentry-guard --probe --node-config /etc/sentry/node_config.json
```

- [ ] Confirm `"pass": true` and `"pi_detected": true`.
- [ ] If any adapter failed, follow its `remediation` array and re-run.

**Do not enable the systemd service or proceed to G2 until G1 `pass=true`.**

```bash
# Only after G1 passes:
sudo systemctl enable --now sentry-guardian
```
