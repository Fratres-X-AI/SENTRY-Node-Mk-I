# SENTRY Rapid Chain Deployment

**Codename:** SENTRY · **Type:** AN/GSQ-100(V)1 · **Date:** 7 June 2026  
**Mode:** Defensive-only · **Mechanical line-thrower only — no explosives**

> **PAPER CONCEPT ONLY FOR Mk I. HAND EMPLACEMENT IS REQUIRED.**
> No launched, thrown, or line-charge deployment is approved for the current COTS hardware.
> The physics/Monte-Carlo modules in `implementation/src/sentry/deployment/` exist to **quantify why**
> mechanical launch destroys COTS internals — not to authorize it. For Mk I, a soldier places each node by hand.

---

## 0. Hand-deployment procedure (the ONLY approved method for Mk I)

For 2–4 nodes covering an approach path or perimeter:

| Step | Action |
|------|--------|
| 1 | Confirm each node passed **G1** (and the reference node passed G2/G3). |
| 2 | Power each node and confirm boot (ACT LED) before walking out. |
| 3 | Emplace nodes **by hand** at **5–10 m spacing** (default **7.5 m**) along the line to watch. |
| 4 | Mount at **2.0 m AGL** on a pole/stake; PIR aimed 15° outward/down. |
| 5 | Keep RTL and LoRa antennas vertical and **≥150 mm apart**. |
| 6 | Maintain **line-of-sight** between mesh neighbors where possible (LoRa tolerates some obstruction). |
| 7 | Label each node; record GPS in the site manifest (`configs/deployment_site_alpha.json`). |
| 8 | Run **G4** to confirm a peer receives an ORANGE OMEN within 5 s. |

**Mesh formation (2–4 nodes):**

- All nodes share one `lora.region`, channel name `SENTRY`, and PSK.
- Node roles in the manifest: `corner`, `gate`, `relay`. A central `relay` improves connectivity.
- There is **no auto-launch self-organization** in Mk I — topology is whatever you physically place plus the peer list in each node config.
- Inbound RX confirmation is **manual via the Meshtastic phone app** (Mk I limitation).

**Spacing quick reference:**

| Nodes | Layout | Spacing | Coverage (approx.) |
|-------|--------|---------|--------------------|
| 2 | Line | 7.5 m | Short approach lane |
| 3 | L / arc | 7.5–10 m | Corner + lane |
| 4 | Rectangle + center relay | 7.5 m | ~240 × 180 m perimeter (datasheet §8) |

---

## 1. Concept (user proposal vs. SENTRY reality)

| Element | Assessment |
|---------|------------|
| Low node mass (~150–300 g) | Feasible for light mechanical throw |
| Passive sensors | Compatible with defensive mandate |
| Connected line (5–10 m spacing) | Modeled; **single break = chain failure risk** |
| Line-charge / rocket launch | **Rejected for COTS** — hundreds of g destroys Pi, RTL-SDR, MEMS |
| Meshtastic post-landing | **Unreliable** without antenna deploy + stable orientation |

**BLUNT:** Hand-emplace or **soft pneumatic** line throw is the minimum aligned with soldier-safety and cheap COTS. Line-charge reference mode exists in simulation **only** to quantify destruction.

---

## 2. Software map

| Module | Path | Role |
|--------|------|------|
| Line physics | `deployment/physics.py` | Tension, peak g, per-node survival |
| Chain topology | `deployment/chain_topology.py` | Linear chain, upstream/downstream IDs |
| Post-landing BIT | `deployment/post_landing.py` | Power, tamper, antenna, mesh readiness |
| Lifecycle | `deployment/manager.py` | stowed → deploying → deployed → chain_joining → operational |
| GPU Monte Carlo | `deployment/monte_carlo_impact.py` | 50k+ impact/join scenarios |
| Guardian FSM | `guardian.py` | Suppresses threat alerts until operational |
| Mesh auto-join | `networking/meshtastic_handler.py` | `chain_auto_join()` peer registration |

---

## 3. Guardian deployment phases

```
stowed → deploying → deployed → chain_joining → operational → watch (normal FSM)
```

- During **deploying … chain_joining**: threat levels forced to **CLEAR** (tamper still → **HOLD**).
- After post-landing BIT passes on at least one node: **operational** → normal perimeter watch.

---

## 4. Launch methods (simulation)

| Method | Peak g (stub) | COTS outcome |
|--------|---------------|--------------|
| `hand_emplace` | 8 | Safe |
| `pneumatic_soft` | 35 | Marginal — bench test required |
| `spring_launcher` | 55 | Pi/RTL likely fail |
| `line_charge_reference` | 450 | **Total destruction (model only)** |

Component survival thresholds (paper): Pi 40g, RTL-SDR 25g, MEMS 30g, USB power bank 60g.

---

## 5. Run deployment simulation

```bash
# Full chain sequence (physics + mesh join + post-landing)
sentry-deploy --config configs/deployment_chain_alpha.json

# Monte Carlo (CPU on Pi/CI; GPU on RunPod with SENTRY_FORCE_GPU=1)
sentry-deploy --monte-carlo --total 50000 --gpu
```

Example config: [`configs/deployment_chain_alpha.json`](../configs/deployment_chain_alpha.json)

---

## 6. Refined deployment constraints (HQ)

1. **Spacing:** 5–10 m between nodes; default 7.5 m.
2. **Mass:** Target ≤ 300 g per node excluding enclosure, including regulated USB power bank.
3. **Launch:** Pneumatic or spring **non-explosive** only; soldier-operated.
4. **Chain:** Physical tether for emplacement ordering; mesh is logical overlay (Meshtastic).
5. **Post-landing:** Mandatory BIT before arming detection — no silent false negatives from dead nodes.
6. **Export:** Rocket/explosive integration increases ITAR/EAR exposure — **out of scope**.

---

## 7. Validation gaps (unchanged)

- No shock-table data for Pi Zero 2 W + RTL-SDR combo
- No field entanglement trials
- Antenna deploy mechanism not in BOM
- GPU Monte Carlo ≠ mechanical proof

See [`risk_register.md`](risk_register.md) R9–R14.
