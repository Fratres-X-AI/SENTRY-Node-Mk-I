# SENTRY — Known First-Build Failures & Exact Fixes

**Type:** AN/GSQ-100(V)1 · **Audience:** non-author builder  
**Use:** When any step or gate fails, find the symptom below and apply the exact fix. Do not improvise.

> Format: **Symptom → Root cause → Exact fix.** Commands are copy-paste ready (run on the Pi unless noted).

---

## 1. Power & boot

### 1.1 No boot — no green ACT LED
- **Symptom:** Pi shows no activity LED after power.
- **Root cause:** Brownout (USB power not holding 5 V), bad SD flash, or hub back-powering.
- **Fix:**
  ```bash
  # Off-Pi: measure USB power output with a USB meter -> should hold near 5.0 V
  # Re-flash SD (Imager -> verify). Confirm power into the OUTER micro-USB (PWR).
  ```

### 1.2 Rainbow screen / repeated reboot
- **Symptom:** Boot loops or undervoltage warnings in `dmesg`.
- **Root cause:** Insufficient current (weak power bank / thin cable / unpowered hub).
- **Fix:**
  ```bash
  dmesg | grep -i voltage   # look for "Under-voltage detected"
  # Use 5V 2.5A supply and 20AWG+ power leads; shorten cable run.
  ```

### 1.3 Power bank will not power node / cuts out under load
- **Symptom:** Node dies when RTL sweep starts.
- **Root cause:** Undercharged pack, weak USB cable, or power bank auto-sleep.
- **Fix:** Charge the pack, use a short high-current USB cable, and verify the bank stays awake under the Pi + USB hub load.

---

## 2. RTL-SDR (RF / G2)

### 2.1 `rtl_test`: "usb_claim_interface error -6"
- **Symptom:** Device busy / cannot claim.
- **Root cause:** Kernel DVB driver `dvb_usb_rtl28xxu` grabbed the dongle.
- **Fix:**
  ```bash
  echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/rtl-sdr-blacklist.conf
  sudo rmmod dvb_usb_rtl28xxu 2>/dev/null || true
  sudo reboot
  rtl_test -t   # expect "Found 1 device(s)"
  ```

### 2.2 `rtl_test`: "No supported devices found"
- **Symptom:** Nothing detected.
- **Root cause:** Power (unpowered hub), bad cable, or dongle dead.
- **Fix:** Move RTL to a powered hub port; try a known-good USB cable; `lsusb | grep -i realtek`.

### 2.3 G2 never shows `rf_burst_2g4`
- **Symptom:** Emitter on, no RF flag.
- **Root cause:** Non-TCXO clone drift, antenna detached/co-located with LoRa, emitter too far.
- **Fix:** Use the specified RTL-SDR Blog V4; separate RTL/LoRa antennas ≥150 mm; place emitter ~1 m; raise `burst_threshold_db` only after confirming geometry.

### 2.4 Permission denied opening RTL
- **Symptom:** Works with `sudo`, fails as user.
- **Root cause:** udev rule / group not applied.
- **Fix:**
  ```bash
  sudo cp deploy/99-sentry.rules /etc/udev/rules.d/
  sudo udevadm control --reload-rules && sudo udevadm trigger
  sudo usermod -aG plugdev,sentry $USER && sudo reboot
  ```

---

## 3. Audio / microphone (G3)

### 3.1 `arecord -l` shows no USB card
- **Symptom:** No capture device.
- **Root cause:** Unpowered hub port, UAC driver, or mic dead.
- **Fix:** Replug into powered port; `dmesg | grep -i audio`; try a different USB MEMS mic.

### 3.2 PyAudio import/build failure during pip install
- **Symptom:** `portaudio.h: No such file`.
- **Root cause:** Missing system PortAudio dev headers.
- **Fix:**
  ```bash
  sudo apt-get install -y portaudio19-dev libatlas-base-dev
  pip install -e "implementation[hardware]"
  ```

### 3.3 G3 never shows `acoustic_propeller_peak`
- **Symptom:** Tone playing, no peak.
- **Root cause:** Tone outside 100–500 Hz band, wind/noise rejection, or gain too low.
- **Fix:** Use a clean **220 Hz** tone at moderate volume ~5 m; remove wind muff for bench test; verify `band_low_hz`/`band_high_hz` in node config.

---

## 4. Meshtastic (G4)

### 4.1 No `/dev/ttyACM0` and no `/dev/meshtastic`
- **Symptom:** Serial device absent.
- **Root cause:** CP210x/CDC driver, cable is charge-only, or udev symlink missing.
- **Fix:**
  ```bash
  lsusb            # expect Silicon Labs CP210x (10c4:ea60) or Adafruit (239a:*)
  ls -l /dev/ttyACM* /dev/ttyUSB*
  sudo cp deploy/99-sentry.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger
  ```

### 4.2 Serial port conflict (serial console grabbing UART)
- **Symptom:** Meshtastic CLI times out or garbled.
- **Root cause:** Login shell on serial, or two processes opening the port.
- **Fix:**
  ```bash
  sudo raspi-config nonint do_serial_cons 1   # disable serial login shell
  sudo systemctl stop sentry-guardian          # stop service before manual CLI use
  ```

### 4.3 Wrong radio variant
- **Symptom:** Meshtastic firmware won't run / wrong region behavior.
- **Root cause:** Wrong LoRa region, wrong serial bridge, or non-Meshtastic-compatible radio firmware.
- **Fix:** Confirm the Waveshare 915 MHz LoRa HAT/bridge is set for the legal local region and visible at `/dev/ttyACM0` or `/dev/meshtastic`. Reflash compatible firmware for the exact board variant.

### 4.4 Peer never receives ORANGE (G4)
- **Symptom:** TX node alerts, peer silent.
- **Root cause:** Different channel/region/PSK, or RX is the manual placeholder.
- **Fix:** Match `lora.region`, channel name `SENTRY`, and PSK on all nodes; **confirm receipt in the Meshtastic phone app** (RX is manual for Mk I).

---

## 5. GPIO (PIR / tamper)

### 5.1 PIR always reads 0 / always 1
- **Symptom:** No motion events or stuck-high.
- **Root cause:** Miswired pin (11 vs 12), HC-SR501 trim pots, or retrigger jumper.
- **Fix:** Confirm OUT → **pin 11 (GPIO17)**; set HC-SR501 sensitivity/time pots mid-range; set jumper to repeat-trigger (H).

### 5.2 Tamper always "tamper_detected"
- **Symptom:** Constant HOLD.
- **Root cause:** Reed not aligned with lid magnet, or wrong pull config.
- **Fix:** Align the switch so the case holds it closed; confirm GPIO21 (physical pin 40) to GND (physical pin 39). Closed case should read LOW; opened case should read HIGH.

### 5.3 GPIO permission denied
- **Symptom:** `RuntimeError: No access to /dev/gpiomem`.
- **Fix:**
  ```bash
  sudo usermod -aG gpio $USER && sudo reboot
  ```

---

## 6. Software / environment

### 6.1 `pip install -e` fails: "project.version must be pep440"
- **Symptom:** Editable install aborts.
- **Root cause:** Non-PEP440 version string in `pyproject.toml`.
- **Fix:** Version must be PEP 440 compliant, for example `0.5.0` rather than `0.5.0-darkspace-integrated`.

### 6.2 `sentry-guard: command not found`
- **Symptom:** Entry point missing.
- **Root cause:** venv not activated or package not installed.
- **Fix:**
  ```bash
  source /opt/sentry-node-mk-i/.venv/bin/activate
  pip install -e "/opt/sentry-node-mk-i/implementation[hardware]"
  ```

### 6.3 Probe runs but `pi_detected: false` on a real Pi
- **Symptom:** G1 fails only on the Pi-detect check.
- **Root cause:** `/proc/device-tree/model` unreadable in container/chroot.
- **Fix:** Run natively (not in a container); confirm `cat /proc/device-tree/model` shows "Raspberry Pi".

---

## 7. Thermal & soak (G5)

### 7.1 Thermal throttle during soak
- **Symptom:** `any_throttled: true`, performance drops.
- **Root cause:** Sealed enclosure heat soak, sustained RTL sweep duty.
- **Fix:** Increase duty `sleep_window_s`; add a small heat-spreader to the Pi SoC; verify enclosure shaded.

### 7.2 Mean power > 5 W
- **Symptom:** G5 `under_target: false`.
- **Root cause:** RTL always-on, no duty cycle, camera enabled.
- **Fix:** Confirm `hardware.duty_cycle.active_window_s`/`sleep_window_s` set; disable visual if unused.

---

## 8. Enclosure & environment

### 8.1 Lid will not close
- **Symptom:** Stack too tall for 165×135×85 mm box.
- **Fix:** Use the **150×120×90 mm** box (datasheet §3.1) or a slimmer USB power bank.

### 8.2 Condensation inside
- **Symptom:** Moisture, corrosion.
- **Fix:** Add desiccant; ensure glands hand-tight+; no free vent holes.

---

## Escalation

If a symptom is not listed, capture:
1. `sentry-guard --probe --node-config /etc/sentry/node_config.json` JSON
2. `dmesg | tail -50`, `lsusb`, `rtl_test -t`, `arecord -l`
3. Photos of wiring

…and file an issue on the repo. **Do not enable the tamper-wipe (`dry_run: false`) or claim field readiness while any gate is failing.**
