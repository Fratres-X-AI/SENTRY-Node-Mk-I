"""Generate configs/nodes/*.json from site manifest."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
base = json.loads((ROOT / "configs" / "sentry_node_config.json").read_text(encoding="utf-8"))
site = json.loads((ROOT / "configs" / "deployment_site_alpha.json").read_text(encoding="utf-8"))
nodes_dir = ROOT / "configs" / "nodes"
nodes_dir.mkdir(exist_ok=True)
all_ids = [n["node_id"] for n in site["nodes"]]
for n in site["nodes"]:
    cfg = json.loads(json.dumps(base))
    cfg["node_id"] = n["node_id"]
    cfg["location"] = n["location"]
    cfg["simulation"] = {
        "enabled": False,
        "fallback_scenario": "benign",
        "rng_seed": 42,
        "sample_rate_hz": 0.5,
    }
    cfg["hardware"]["meshtastic"]["peers"] = [p for p in all_ids if p != n["node_id"]]
    cfg["outputs"]["alert_dir"] = "/var/lib/sentry/alerts"
    cfg["power"]["log_path"] = "/var/lib/sentry/sentry_power.jsonl"
    (nodes_dir / f"{n['node_id']}.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
print(f"Generated {len(all_ids)} node configs in {nodes_dir}")

if __name__ == "__main__":
    pass
