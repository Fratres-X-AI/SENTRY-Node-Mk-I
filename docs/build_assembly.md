# SENTRY Node Mk I — Assembly Procedure

**Type:** AN/GSQ-100(V)1 · **Time:** ~90 min first node · **Tools:** soldering iron (optional for GPIO), screwdriver, zip ties

## Order of assembly (inside → outside)

### 1. Pi prep (15 min)

1. Flash SD per [`sd_flash_checklist.md`](sd_flash_checklist.md) — **do not boot yet** if first mechanical build.
2. Mount Pi Zero 2 W on **12 mm standoffs** inside enclosure lid panel.
3. Route micro-USB OTG to hub location; strain-relief tie point.

### 2. Power (10 min)

1. Mount buck converter; input from LiPo XT30 (through fuse holder recommended).
2. Output **5.0 V** verified with meter before connecting Pi.
3. LiPo flat pack on bottom layer — velcro or bracket; **no puncture risk** against standoffs.

### 3. USB tree (15 min)

Connect to **powered 4-port hub**:

| Port | Device |
|------|--------|
| 1 | RTL-SDR Blog V3 |
| 2 | USB MEMS microphone |
| 3 | Meshtastic T-Beam (USB serial) |
| 4 | spare / debug |

Hub uplink → Pi Zero OTG micro-USB.

### 4. GPIO (10 min)

| Signal | Pi pin | Wire |
|--------|--------|------|
| PIR OUT | GPIO 17 | 3.3 V logic, common ground |
| Tamper reed | GPIO 27 | pull-up, active-low to ground when open |

Run PIR **outside** enclosure on bracket; desiccant inside, glands sealed.

### 5. Antennas (10 min)

| Antenna | Route |
|---------|--------|
| RTL telescopic | M16 gland, vertical, 2.2 m AGL tip target |
| LoRa 868/915 whip | Separate gland, keep 150 mm from RTL if possible |
| MEMS | 150 mm gooseneck, foam wind muff |

### 6. Enclosure close (10 min)

1. Desiccant pack inside.
2. Lid torque even; tamper reed aligned with lid magnet.
3. Cable glands tight; no pinching RF coax.

### 7. Pole mount (20 min)

1. U-bolt enclosure to **50 mm pole** at **2.0 m AGL** sensor reference.
2. PIR aimed 15° outward/down per datasheet.
3. Label node ID (`sentry-pi-zero-00X`) on enclosure + SD hostname.

### 8. First boot software (10 min)

```bash
sudo bash /opt/sentry-node-mk-i/deploy/bootstrap_pi_zero.sh
sentry-guard --probe
```

## 4-node site layout

Use [`configs/deployment_site_alpha.json`](../configs/deployment_site_alpha.json) coordinates or your site survey. One config file per node in [`configs/nodes/`](../configs/nodes/).

## Do not do at build

- Do not enable tamper wipe (`dry_run: false`) until counsel + ops sign-off.
- Do not claim 5.8 GHz detection — RTL cannot tune it.
- Do not line-charge deploy COTS internals — see [`deployment_chain.md`](deployment_chain.md).

## Spares to bag with each node

- 1× extra SD pre-flashed
- 4× desiccant
- 1× USB hub fuse or spare buck
- Node ID sticker + QR to mesh channel config
