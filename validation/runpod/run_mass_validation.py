#!/usr/bin/env python3
"""Parallel Monte Carlo validation for SENTRY on RunPod."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import random
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "implementation" / "src"))

from sentry.guardian import SentryGuardian
from sentry.simulation.synthetic import SimScenario, SimulatedSensorArray, scenario_from_name


@dataclass
class RunResult:
    seed: int
    scenario: str
    max_level: str
    frames: int
    mean_score: float
    elapsed_ms: float


def _one_run(args: tuple[int, str, int]) -> RunResult:
    seed, scenario_name, frames = args
    rng = random.Random(seed)
    scenario = scenario_from_name(scenario_name)
    # Perturb baselines for Monte Carlo spread
    scenario = SimScenario(
        name=scenario.name,
        base_pir=scenario.base_pir + rng.uniform(-0.02, 0.02),
        base_acoustic=scenario.base_acoustic + rng.uniform(-0.02, 0.02),
        base_rf=scenario.base_rf + rng.uniform(-0.01, 0.01),
        base_visual=scenario.base_visual + rng.uniform(-0.02, 0.02),
        intrusion_start_s=scenario.intrusion_start_s,
        intrusion_peak_s=scenario.intrusion_peak_s,
        jamming_start_s=scenario.jamming_start_s,
        low_visibility=scenario.low_visibility,
        propeller_tone_hz=scenario.propeller_tone_hz + rng.uniform(-20, 20),
    )
    sensors = SimulatedSensorArray("sentry-mc", scenario, rng_seed=seed)
    guardian = SentryGuardian("sentry-mc", {})
    t0 = time.perf_counter()
    scores: list[float] = []
    max_level = "CLEAR"
    rank = {"CLEAR": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3, "HOLD": 4}
    for i in range(frames):
        event = sensors.sample(float(i) * 0.5)
        alert = guardian.process(event)
        scores.append(alert.threat_score)
        if rank[alert.level] > rank[max_level]:
            max_level = alert.level
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return RunResult(
        seed=seed,
        scenario=scenario_name,
        max_level=max_level,
        frames=frames,
        mean_score=sum(scores) / len(scores) if scores else 0.0,
        elapsed_ms=elapsed_ms,
    )


def main() -> int:
    workers = int(os.environ.get("SENTRY_WORKERS", max(4, mp.cpu_count() - 2)))
    n_per_scenario = int(os.environ.get("SENTRY_MASS_SCENARIOS", 500))
    seed_start = int(os.environ.get("SENTRY_MASS_SEED_START", 1))
    frames = int(os.environ.get("SENTRY_MASS_FRAMES", 40))
    scenarios = ["benign", "intrusion", "jamming", "low_visibility"]

    tasks: list[tuple[int, str, int]] = []
    for sc in scenarios:
        for i in range(n_per_scenario):
            tasks.append((seed_start + i + hash(sc) % 10000, sc, frames))

    print(f"SENTRY mass validation: {len(tasks)} runs, {workers} workers, {frames} frames/run")
    t0 = time.perf_counter()
    with mp.Pool(workers) as pool:
        results = pool.map(_one_run, tasks, chunksize=max(1, len(tasks) // (workers * 4)))
    wall_s = time.perf_counter() - t0

    by_scenario: dict[str, list[RunResult]] = {s: [] for s in scenarios}
    for r in results:
        by_scenario[r.scenario].append(r)

    report: dict = {
        "codename": "SENTRY",
        "mode": "mass_monte_carlo",
        "host_workers": workers,
        "total_runs": len(results),
        "wall_seconds": round(wall_s, 2),
        "runs_per_second": round(len(results) / wall_s, 1),
        "scenarios": {},
    }

    for sc, runs in by_scenario.items():
        levels = Counter(r.max_level for r in runs)
        times = [r.elapsed_ms for r in runs]
        scores = [r.mean_score for r in runs]
        report["scenarios"][sc] = {
            "runs": len(runs),
            "level_distribution": dict(levels),
            "mean_score_avg": round(sum(scores) / len(scores), 4),
            "latency_ms_mean": round(sum(times) / len(times), 2),
            "latency_ms_p95": round(sorted(times)[int(len(times) * 0.95)], 2),
        }

    # Acceptance heuristics (simulation-only)
    jamming_hold_rate = by_scenario["jamming"]
    hold_pct = sum(1 for r in jamming_hold_rate if r.max_level == "HOLD") / max(len(jamming_hold_rate), 1)
    benign_clear_pct = sum(1 for r in by_scenario["benign"] if r.max_level in {"CLEAR", "YELLOW"}) / max(
        len(by_scenario["benign"]), 1
    )
    report["acceptance"] = {
        "jamming_hold_rate": round(hold_pct, 4),
        "benign_low_rate": round(benign_clear_pct, 4),
        "pass": hold_pct >= 0.85 and benign_clear_pct >= 0.90,
    }
    report["overall"] = "PASS" if report["acceptance"]["pass"] else "FAIL"

    out_dir = ROOT / "validation" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "runpod-mass-validation.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
