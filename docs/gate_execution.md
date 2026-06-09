# SENTRY Acceptance Gates G1–G5 — Execution Guide

**Type:** AN/GSQ-100(V)1 · **Run location:** on the Pi (node) unless noted  
**Mode:** Defensive-only · Receive-only

> Run gates **in order**. Do not advance until the prior gate passes (G1) or is manually confirmed (G2–G5).
> Every gate writes a JSON report to `validation/reports/gate-gN.json`.

Common prerequisites:

```bash
cd /opt/sentry-node-mk-i
source .venv/bin/activate
export PYTHONPATH=/opt/sentry-node-mk-i/implementation/src
```

---

## G1 — Hardware probe (Built-In Test)

**Proves:** every required sensor/driver enumerates on the Pi.

**Command:**

```bash
sentry-guard --probe --node-config /etc/sentry/node_config.json
# equivalent full harness:
python validation/run_gate.py --gate G1
```

**Expected output (excerpt):**

```json
{
  "gate": "G1",
  "pi_detected": true,
  "available_count": 5,
  "total_count": 6,
  "failures": [],
  "pass": true,
  "pass_criteria": "All required adapters available AND running on Raspberry Pi hardware."
}
```

**Troubleshooting tree:**

- `pass:false` and a `failures[]` entry → run that entry's `remediation` steps verbatim.
- `pi_detected:false` on a real Pi → see `known_first_build_failures.md` §6.3.
- `rf_sensor` failed → §2 (DVB blacklist, TCXO).
- `meshtastic_handler` failed → §4 (udev, serial, SX1262).

**Pass criteria (plain language):** Running on a Raspberry Pi, and PIR, acoustic, RF, tamper, and Meshtastic all report available. Visual is optional.

---

## G2 — RF 2.4 GHz burst detection

**Proves:** the RTL-SDR sees real 2.4 GHz energy and raises `rf_burst_2g4`.

**Setup:** Place a 2.4 GHz source (Wi-Fi AP or phone hotspot, actively transferring data) ~1–2 m from the RTL antenna.

**Command:**

```bash
python validation/run_gate.py --gate G2
# then run a live capture and watch for the flag:
sentry-guard --live --duration 60 --node-config /etc/sentry/node_config.json
```

**Expected:** during live capture, at least one alert frame contains `"rf_burst_2g4": true` (or an elevated `rf` channel) **while the emitter is on**, and **not** when it is off.

**Troubleshooting tree:**

- No flag with emitter on → §2.3 (TCXO, antenna separation, distance).
- RTL unavailable → fix G1 first.
- Flag present with emitter off → ambient 2.4 GHz; move to a quieter area or raise `burst_threshold_db`.

**Pass criteria:** `rf_burst_2g4` appears only when the emitter is active. Toggle the emitter to confirm causality.

---

## G3 — Acoustic 220 Hz peak

**Proves:** the mic + FFT detects a tone in the 100–500 Hz band.

**Setup:** Play a steady **220 Hz** tone from a speaker ~5 m from the mic.

**Command:**

```bash
python validation/run_gate.py --gate G3
sentry-guard --live --duration 60 --node-config /etc/sentry/node_config.json
```

**Expected:** alert frames contain `"acoustic_propeller_peak": true` while the tone plays; absent in silence.

**Troubleshooting tree:**

- Mic unavailable → §3.1/§3.2.
- No peak with tone → §3.3 (frequency, volume, band config, remove wind muff for bench).

**Pass criteria:** `acoustic_propeller_peak` tracks the tone on/off.

---

## G4 — 4-node mesh ORANGE relay

**Proves:** an ORANGE alert on one node reaches a peer over Meshtastic within 5 s.

**Setup:** Power **≥2 nodes**, same `lora.region`, channel `SENTRY`, same PSK. Have the Meshtastic phone app paired to confirm RX (Mk I RX is manual).

**Command (on each node):**

```bash
python validation/run_gate.py --gate G4
```

Then trigger ORANGE on one node using a G2/G3 stimulus and observe the peer / app.

**Expected:** peer node inbox or Meshtastic app shows an `omen_alert.v1` with `"level":"ORANGE"` within 5 s.

**Troubleshooting tree:**

- Device absent → §4.1.
- Serial conflict → §4.2.
- Peer silent → §4.4 (match region/channel/PSK; confirm in app).

**Pass criteria:** ORANGE OMEN received on a peer within 5 s of trigger.

---

## G5 — Soak / power & thermal budget

**Proves:** the node runs 8 h under 5 W average with no thermal throttle.

**Short sample (sanity):**

```bash
python validation/run_gate.py --gate G5 --soak-minutes 480
```

(The harness samples a short window live; the **full** gate is the 8 h service run below.)

**Full soak:**

```bash
sudo systemctl enable --now sentry-guardian
# leave running 8 h, then:
python - <<'PY'
import json, pathlib
p = pathlib.Path("/var/lib/sentry/sentry_power.jsonl")
rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
w = [r["estimated_watts"] for r in rows]
print("samples", len(w), "mean_W", round(sum(w)/len(w),2), "max_W", round(max(w),2))
PY
```

**Expected:** mean watts < 5.0, no `any_throttled: true`.

**Troubleshooting tree:**

- Throttle → §7.1 (duty cycle, heat spreader, shade).
- Mean > 5 W → §7.2 (RTL duty, disable visual).

**Pass criteria:** Mean power < 5 W AND no thermal throttle across 8 h.

---

## Gate completion log (fill in)

| Gate | Date | Operator | Result | Report file |
|------|------|----------|--------|-------------|
| G1 | | | ☐ PASS ☐ FAIL | `validation/reports/gate-g1.json` |
| G2 | | | ☐ PASS ☐ FAIL | `validation/reports/gate-g2.json` |
| G3 | | | ☐ PASS ☐ FAIL | `validation/reports/gate-g3.json` |
| G4 | | | ☐ PASS ☐ FAIL | `validation/reports/gate-g4.json` |
| G5 | | | ☐ PASS ☐ FAIL | `validation/reports/gate-g5.json` |

**Field-ready = all five PASS on real hardware.** Until then, SENTRY is build-stage only.
