#!/usr/bin/env python3
"""Simulated 4-node Meshtastic mesh soak — thousands of alert relays."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "implementation" / "src"))

from sentry.networking.meshtastic_handler import MeshNodeConfig, MeshtasticHandler, MeshtasticHandlerConfig


def _node_worker(args: tuple[str, int, str]) -> dict:
    node_id, n_alerts, spool_base = args
    spool = Path(spool_base) / f"{node_id}_spool.jsonl"
    cfg = MeshtasticHandlerConfig(
        local=MeshNodeConfig(node_id=node_id),
        spool_path=spool,
    )
    handler = MeshtasticHandler(cfg)
    t0 = time.perf_counter()
    sent = 0
    for i in range(n_alerts):
        ok = handler.send_alert(
            {
                "node_id": node_id,
                "level": "ORANGE" if i % 3 else "RED",
                "threat_score": 0.6 + (i % 10) * 0.03,
                "seq": i,
                "timestamp_s": time.time(),
            }
        )
        if ok:
            sent += 1
    handler.close()
    elapsed = time.perf_counter() - t0
    return {"node_id": node_id, "sent": sent, "elapsed_s": round(elapsed, 3)}


def main() -> int:
    workers = int(os.environ.get("SENTRY_MESH_WORKERS", 4))
    nodes = [f"sentry-pi-zero-{i:03d}" for i in range(1, 5)]
    alerts_per_node = int(os.environ.get("SENTRY_MESH_ALERTS", 2500))
    spool_base = os.environ.get("SENTRY_MESH_SPOOL", "/tmp/sentry_mesh_soak")
    Path(spool_base).mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    with mp.Pool(workers) as pool:
        results = pool.map(
            _node_worker,
            [(n, alerts_per_node, spool_base) for n in nodes],
        )
    wall = time.perf_counter() - t0
    total_sent = sum(r["sent"] for r in results)
    total_lines = 0
    for n in nodes:
        spool = Path(spool_base) / f"{n}_spool.jsonl"
        if spool.exists():
            total_lines += sum(1 for _ in spool.open())

    report = {
        "codename": "SENTRY",
        "mode": "mesh_soak_simulation",
        "nodes": nodes,
        "alerts_per_node": alerts_per_node,
        "total_sent": total_sent,
        "total_spool_lines": total_lines,
        "wall_seconds": round(wall, 3),
        "alerts_per_second": round(total_sent / wall, 1),
        "node_results": results,
        "pass": total_sent == len(nodes) * alerts_per_node,
        "overall": "PASS" if total_sent == len(nodes) * alerts_per_node else "FAIL",
    }
    out_dir = ROOT / "validation" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "runpod-mesh-soak.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
