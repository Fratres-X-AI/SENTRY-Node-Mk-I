"""SENTRY Mk I pre-physical chaos and stress simulator."""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

TARGET_PIPE = Path("validation/reports/chaos_stream.json")
ITERATIONS = 1000
BURST_RATE = 0.001


class ChaosEngine:
    def __init__(self) -> None:
        self.base_event = {
            "node_id": "AN-GSQ-100-V1-ALPHA",
            "timestamp": "2026-06-10T07:30:00Z",
            "sequence_id": 1000,
            "metrics": {"rf_2g4_dbm": -85.0, "rf_5g8_dbm": -90.0, "acoustic_fft_peak_hz": 0.0},
            "hmac_signature": "8f9e6a7b2c4d5e6f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f",
        }

    def generate_malformed_json(self) -> str:
        raw_str = json.dumps(self.base_event)
        truncate_point = random.randint(10, len(raw_str) - 5)
        return raw_str[:truncate_point]

    def generate_type_bomb(self) -> str:
        bad_data = json.loads(json.dumps(self.base_event))
        bad_data["metrics"]["acoustic_fft_peak_hz"] = "NaN_STRING_BOMB"
        bad_data["sequence_id"] = [1, 2, 3, "overflow"]
        bad_data["timestamp"] = None
        return json.dumps(bad_data)

    def generate_data_flood(self) -> str:
        flood_data = json.loads(json.dumps(self.base_event))
        flood_data["sequence_id"] = random.randint(5000, 99999)
        flood_data["metrics"]["rf_2g4_dbm"] = random.uniform(-20.0, -10.0)
        flood_data["metrics"]["acoustic_fft_peak_hz"] = random.uniform(100.0, 500.0)
        return json.dumps(flood_data)

    def generate_jamming_hold(self) -> str:
        hold_data = json.loads(json.dumps(self.base_event))
        hold_data["metrics"]["rf_2g4_dbm"] = 10.0
        hold_data["metrics"]["rf_5g8_dbm"] = 10.0
        return json.dumps(hold_data)


def run_chaos_test() -> None:
    engine = ChaosEngine()
    TARGET_PIPE.parent.mkdir(parents=True, exist_ok=True)
    metrics = {"malformed": 0, "type_bomb": 0, "flood": 0, "jam_hold": 0}

    with TARGET_PIPE.open("w", encoding="utf-8") as fh:
        for _ in range(ITERATIONS):
            choice = random.choice(["malformed", "type_bomb", "flood", "jam_hold"])
            metrics[choice] += 1
            if choice == "malformed":
                payload = engine.generate_malformed_json()
            elif choice == "type_bomb":
                payload = engine.generate_type_bomb()
            elif choice == "flood":
                payload = engine.generate_data_flood()
            else:
                payload = engine.generate_jamming_hold()
            fh.write(payload + "\n")
            time.sleep(BURST_RATE)

    print(json.dumps({"events": ITERATIONS, **metrics, "target": str(TARGET_PIPE)}, indent=2))


if __name__ == "__main__":
    run_chaos_test()
