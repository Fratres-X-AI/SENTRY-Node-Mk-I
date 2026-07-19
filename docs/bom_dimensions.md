# SENTRY Bill of Materials — Dimensions & Mass

**Type designation:** AN/GSQ-100(V)1 · SENTRY Node Mk I  
**Per-node physical build sheet.** Pair with [`system_datasheet.md`](system_datasheet.md).

## Core electronics (inside enclosure)

| Item | L × W × H (mm) | Mass | Notes |
|------|----------------|------|-------|
| Raspberry Pi Zero 2 W | 65 × 30 × 5 | 12 g | Quad-core 1 GHz, 512 MB RAM |
| RTL-SDR Blog V4 Dongle | 95 × 25 × 10 | 25 g | Antenna adds 120 mm length |
| Waveshare LoRa HAT (915MHz) | 65 × 30 × 20 | 30 g | Meshtastic-compatible LoRa relay path |
| USB Mini Microphone | 60 × 18 × 8 | 15 g | On 150 mm gooseneck |
| HC-SR501 PIR | 32 × 24 × 24 | 20 g | Outside enclosure face |
| Anker PowerCore 10,000 mAh | 100 × 60 × 22 | 180 g | Regulated USB power bank |
| Powered USB hub | 80 × 45 × 15 | 30 g | 4-port micro OTG |

## Enclosure & mount

| Item | L × W × H (mm) | Mass |
|------|----------------|------|
| IP67 rugged enclosure (recommended) | **165 × 135 × 85** | 450 g |
| Alternate (more headroom) | **150 × 120 × 90** | 480 g |
| Pole 50 mm OD × 2.5 m | 2500 × 50 dia | 3000 g |
| U-bolt + bracket | — | 200 g |

## Site totals (4-node mesh)

| Category | Mass | Cost (est.) |
|----------|------|-------------|
| Electronics × 4 | ~1.9 kg | ~$864 |
| Enclosures × 4 | ~1.8 kg | ~$100 |
| Mounting kits × 4 | ~1 kg | ~$40 |
| **Site total** | **~5 kg plus mounts** | **~$864** |

Excludes labour, shipping, spares, test equipment.

## Spares kit (recommended)

| Item | Qty |
|------|-----|
| Pi Zero 2 W | 1 |
| RTL-SDR Blog V4 | 1 |
| USB hub | 1 |
| Power bank | 1 |
| SD card pre-flashed | 2 |
| Desiccant packs | 4 |
