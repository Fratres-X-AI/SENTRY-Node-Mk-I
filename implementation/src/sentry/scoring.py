"""Threat scoring and alert level assignment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ThreatThresholds:
    yellow: float = 0.35
    orange: float = 0.55
    red: float = 0.75
    jamming_hold: float = 0.90

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> ThreatThresholds:
        t = cfg.get("thresholds", cfg)
        return cls(
            yellow=float(t.get("yellow_score", 0.35)),
            orange=float(t.get("orange_score", 0.55)),
            red=float(t.get("red_score", 0.75)),
            jamming_hold=float(t.get("jamming_hold_score", 0.90)),
        )


class ThreatScorer:
    """Maps fused sensor evidence to defensive alert levels."""

    def score(self, fused: dict[str, Any], thresholds: ThreatThresholds) -> dict[str, Any]:
        threat_score = float(fused["fused_score"])
        flags = fused.get("flags", {})
        jamming = bool(flags.get("jamming_suspected"))

        if jamming and threat_score >= thresholds.orange:
            level = "HOLD"
            rationale = "RF jamming suspected with elevated fused score — hold-safe (no automated action)"
        elif threat_score >= thresholds.red:
            level = "RED"
            rationale = "High fused threat score — early warning RED"
        elif threat_score >= thresholds.orange:
            level = "ORANGE"
            rationale = "Elevated fused threat score — early warning ORANGE"
        elif threat_score >= thresholds.yellow:
            level = "YELLOW"
            rationale = "Moderate fused activity — early warning YELLOW"
        else:
            level = "CLEAR"
            rationale = "Baseline passive watch — no elevated threat"

        if flags.get("steganography_suspected") and level == "CLEAR":
            level = "YELLOW"
            rationale = "DARKSPACE whisper entropy anomaly — early warning YELLOW"
        if flags.get("passive_network_anomaly") and threat_score >= thresholds.yellow and level in {"CLEAR", "YELLOW"}:
            level = "ORANGE"
            rationale = "DARKSPACE passive network anomaly with elevated score — early warning ORANGE"

        return {
            "threat_score": threat_score,
            "level": level,
            "rationale": rationale,
            "jamming_suspected": jamming,
        }
