"""Guardian state machine — passive perimeter watch with power/duty integration."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from sentry.deployment.manager import DeploymentManager
from sentry.fusion import SensorFusion
from sentry.scoring import ThreatScorer, ThreatThresholds
from sentry.sensors.power_metrics import PowerMetrics, PowerMetricsConfig
from sentry.types import AlertFrame, SensorEvent

LOG = logging.getLogger("SENTRY")


@dataclass
class GuardianConfig:
    dwell_confirm_s: float = 3.0
    cooldown_s: float = 30.0
    perimeter_radius_m: float = 120.0
    sleep_in_idle_s: float = 0.0


class SentryGuardian:
    """Orchestrates fusion, scoring, power metrics, and defensive early-warning alerts."""

    def __init__(
        self,
        node_id: str,
        mission: dict[str, Any] | None = None,
        power_metrics: PowerMetrics | None = None,
    ) -> None:
        mission = mission or {}
        guardian_cfg = mission.get("guardian", {})
        self.node_id = node_id
        self.config = GuardianConfig(
            dwell_confirm_s=float(guardian_cfg.get("dwell_confirm_s", 3.0)),
            cooldown_s=float(guardian_cfg.get("cooldown_s", 30.0)),
            perimeter_radius_m=float(guardian_cfg.get("perimeter_radius_m", 120.0)),
            sleep_in_idle_s=float(guardian_cfg.get("sleep_in_idle_s", 0.0)),
        )
        self.thresholds = ThreatThresholds.from_config(mission)
        self.fusion = SensorFusion(mission.get("sensors", {}))
        self.scorer = ThreatScorer()
        self.power = power_metrics
        self.deployment = DeploymentManager.from_mission(mission)
        self._seq = 0
        self._state = "watch"
        self._elevated_since: float | None = None
        self._cooldown_until: float = 0.0
        self._last_level = "CLEAR"

    def run_deployment_sequence(self) -> dict[str, Any]:
        """Mechanical line chain: launch → mesh auto-join → post-landing BIT."""
        if self.deployment is None:
            return {"error": "deployment not enabled in mission profile"}
        return self.deployment.full_deploy_sequence()

    def deployment_summary(self) -> dict[str, Any]:
        if self.deployment is None:
            return {"enabled": False}
        return {"enabled": True, **self.deployment.state.to_dict()}

    def process(self, event: SensorEvent) -> AlertFrame:
        duty_active = bool(event.flags.get("hardware_active_window", True))
        if self.power is not None:
            self.power.record(
                duty_active=duty_active,
                rtl_active=duty_active and event.flags.get("rf_source") == "rtl_power",
                acoustic_active=duty_active,
                lora_tx=False,
            )

        fused = self.fusion.fuse(event)
        scored = self.scorer.score(fused, self.thresholds)

        # Boost explainability for EW/acoustic signatures
        if event.flags.get("rf_burst_2g4") or event.flags.get("rf_burst_5g8"):
            scored["rationale"] += " | RF burst detected"
        if event.flags.get("acoustic_propeller_peak"):
            scored["rationale"] += " | 100-500Hz propeller peak"

        level = scored["level"]
        ts = event.timestamp_s

        if event.flags.get("tamper_detected"):
            level = "HOLD"
            scored["level"] = level
            scored["rationale"] = "Enclosure tamper — hold-safe"

        # Deployment lifecycle: suppress threat tiers until chain operational
        if self.deployment is not None and self.deployment.alerts_suppressed():
            dep_phase = self.deployment.guardian_state_label()
            self._state = dep_phase
            if level not in {"HOLD"}:
                level = "CLEAR"
                scored["level"] = level
                scored["rationale"] = f"Deployment phase {dep_phase} — threat alerts suppressed"
            alert = AlertFrame(
                node_id=self.node_id,
                seq=self._seq,
                timestamp_s=ts,
                level=level,
                threat_score=float(scored["threat_score"]),
                rationale=str(scored["rationale"]),
                guardian_state=self._state,
                sensor_event=event.to_dict(),
            )
            self._seq += 1
            return alert

        if ts < self._cooldown_until and level in {"YELLOW", "ORANGE"}:
            level = self._last_level if self._last_level != "CLEAR" else "CLEAR"
            scored["level"] = level
            scored["rationale"] = "Guardian cooldown — suppressing repeat low-tier alert"

        if level in {"ORANGE", "RED", "HOLD"}:
            if self._elevated_since is None:
                self._elevated_since = ts
            dwell = ts - self._elevated_since
            if dwell < self.config.dwell_confirm_s and level != "HOLD":
                self._state = "confirming"
                scored["level"] = "YELLOW"
                scored["rationale"] = f"Dwell confirm {dwell:.1f}s / {self.config.dwell_confirm_s:.1f}s"
                level = "YELLOW"
            else:
                self._state = "alerting" if level != "HOLD" else "hold_safe"
        elif level == "YELLOW":
            self._state = "watch"
            self._elevated_since = ts
        else:
            self._state = "watch"
            self._elevated_since = None
            if self._last_level in {"ORANGE", "RED"}:
                self._cooldown_until = ts + self.config.cooldown_s
                self._state = "cooldown"
            if self.config.sleep_in_idle_s > 0 and level == "CLEAR":
                time.sleep(min(self.config.sleep_in_idle_s, 0.5))

        self._last_level = level

        alert = AlertFrame(
            node_id=self.node_id,
            seq=self._seq,
            timestamp_s=ts,
            level=level,
            threat_score=float(scored["threat_score"]),
            rationale=str(scored["rationale"]),
            guardian_state=self._state,
            sensor_event=event.to_dict(),
        )
        self._seq += 1
        return alert

    def power_summary(self) -> dict[str, Any]:
        if self.power is None:
            return {}
        return self.power.summary()
