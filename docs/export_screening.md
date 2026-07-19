# Export Control Screening — SENTRY

**Codename:** SENTRY · **Date:** 7 June 2026  
**Status:** Internal screening draft — **not a legal determination**

## Scope

SENTRY v0.5.0-darkspace-integrated is a **passive sensing stack** with one low-power alert relay:

| Component | Transmit? | Notes |
|-----------|-----------|-------|
| RTL-SDR (`rtl_power`) | No | Passive spectrum read |
| USB microphone / acoustic FFT | No | Listen-only |
| PIR / GPIO tamper | No | Digital inputs |
| Meshtastic relay | Yes (LoRa) | Low-power mesh alert text only — review local RF rules |
| Camera motion | No | Local processing |

## Items requiring counsel review

- RTL2832U SDR dongle export classification (country-dependent)
- Meshtastic LoRa hardware frequency plan vs destination ITU region
- Any future addition of **transmit** counter-jam or active EW

## Repository stance

- No ITAR-controlled technical data identified by engineering review of this repo
- No classified sources used
- **Fratres X AI compliance officer review required** before foreign disclosure, sale, or field deployment outside authorized jurisdiction

## Next action

Complete formal export screening worksheet and file result here before hardware procurement ships internationally.
