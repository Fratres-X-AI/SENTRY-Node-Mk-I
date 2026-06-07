"""Multi-channel sensor fusion for SENTRY."""

from __future__ import annotations

from typing import Any

from sentry.types import SensorEvent


class SensorFusion:
    """Weighted passive-sensor fusion with jamming/visibility modifiers."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = weights or {
            "pir_weight": 0.30,
            "acoustic_weight": 0.25,
            "rf_weight": 0.20,
            "visual_weight": 0.25,
        }

    def fuse(self, event: SensorEvent) -> dict[str, Any]:
        ch = event.channels
        w_pir = float(self.weights.get("pir_weight", 0.30))
        w_ac = float(self.weights.get("acoustic_weight", 0.25))
        w_rf = float(self.weights.get("rf_weight", 0.20))
        w_vis = float(self.weights.get("visual_weight", 0.25))

        fused_score = (
            w_pir * ch.pir
            + w_ac * ch.acoustic
            + w_rf * ch.rf
            + w_vis * ch.visual
        )

        if event.flags.get("low_visibility"):
            fused_score *= 0.85

        if event.flags.get("jamming_suspected"):
            fused_score = max(fused_score, ch.rf * 0.95)

        return {
            "fused_score": min(1.0, fused_score),
            "channel_contributions": {
                "pir": w_pir * ch.pir,
                "acoustic": w_ac * ch.acoustic,
                "rf": w_rf * ch.rf,
                "visual": w_vis * ch.visual,
            },
            "flags": dict(event.flags),
        }
