# SENTRY Bill of Materials — Dimensions & Mass

**Type designation:** AN/GSQ-100(V)1 · SENTRY Node Mk I  
**Per-node physical build sheet.** Pair with [`system_datasheet.md`](system_datasheet.md).

## Core electronics (inside enclosure)

| Item | L × W × H (mm) | Mass | Notes |
|------|----------------|------|-------|
| Raspberry Pi Zero 2 W | 65 × 30 × 5 | 12 g | Quad-core 1 GHz, 512 MB RAM |
| RTL-SDR Blog V3 (PCB) | 95 × 25 × 10 | 25 g | Antenna adds 120 mm length |
| LilyGO T-Beam v1.1 | 100 × 25 × 20 | 80 g | SX1262 + ESP32 |
| USB MEMS dongle | 60 × 18 × 8 | 15 g | On 150 mm gooseneck |
| HC-SR501 PIR | 32 × 24 × 24 | 20 g | Outside enclosure face |
| 2S LiPo 5000 mAh flat | 130 × 70 × 18 | 280 g | Largest mass item |
| Powered USB hub | 80 × 45 × 15 | 30 g | 4-port micro OTG |
| Buck 5 V 2.5 A | 45 × 30 × 10 | 10 g | ≥85 % efficiency |

## Enclosure & mount

| Item | L × W × H (mm) | Mass |
|------|----------------|------|
| IP65 ABS box (recommended) | **165 × 135 × 85** | 450 g |
| Alternate (more headroom) | **150 × 120 × 90** | 480 g |
| Pole 50 mm OD × 2.5 m | 2500 × 50 dia | 3000 g |
| U-bolt + bracket | — | 200 g |

## Site totals (4-node mesh)

| Category | Mass | Cost (est.) |
|----------|------|-------------|
| Electronics × 4 | ~1.9 kg | ~$864 |
| Enclosures × 4 | ~1.8 kg | ~$72 |
| Poles × 4 | ~12 kg | ~$120 |
| **Site total** | **~16 kg** | **~$1,056** |

Excludes labour, shipping, spares, test equipment.

## Spares kit (recommended)

| Item | Qty |
|------|-----|
| Pi Zero 2 W | 1 |
| RTL-SDR | 1 |
| USB hub | 1 |
| LiPo | 1 |
| SD card pre-flashed | 2 |
| Desiccant packs | 4 |
