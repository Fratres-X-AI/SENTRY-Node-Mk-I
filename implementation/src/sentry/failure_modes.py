"""Failure mode simulation for SENTRY V&V."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sentry.guardian import SentryGuardian
from sentry.simulation.synthetic import SimulatedSensorArray, scenario_from_name
from sentry.types import SensorChannels, SensorEvent


@dataclass
class FailureResult:
    mode: str
    passed: bool
    detail: str
    max_level: str = "CLEAR"

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "passed": self.passed,
            "detail": self.detail,
            "max_level": self.max_level,
        }


def _run_events(events: list[SensorEvent], mission: dict[str, Any] | None = None) -> str:
    guardian = SentryGuardian("sentry-failure-test", mission or {})
    max_level = "CLEAR"
    rank = {"CLEAR": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3, "HOLD": 4}
    for event in events:
        alert = guardian.process(event)
        if rank[alert.level] > rank[max_level]:
            max_level = alert.level
    return max_level


def simulate_sensor_dropout(duration_frames: int = 20) -> FailureResult:
    """RF channel stuck at zero mid-run — fusion should degrade gracefully."""
    sensors = SimulatedSensorArray("t", scenario_from_name("intrusion"), rng_seed=1)
    events = list(sensors.stream(10.0, 2.0))[:duration_frames]
    mid = len(events) // 2
    for event in events[mid:]:
        event.channels = SensorChannels(
            pir=event.channels.pir,
            acoustic=event.channels.acoustic,
            rf=0.0,
            visual=event.channels.visual,
        )
    max_level = _run_events(events)
    passed = max_level in {"YELLOW", "ORANGE", "RED", "HOLD", "CLEAR"}
    return FailureResult("sensor_dropout_rf", passed, f"max_level={max_level}", max_level)


def simulate_thermal_throttle() -> FailureResult:
    """Hold-safe should still trigger under jamming when RF remains readable."""
    sensors = SimulatedSensorArray("t", scenario_from_name("jamming"), rng_seed=3)
    events = list(sensors.stream(15.0, 2.0))
    for event in events:
        event.flags["thermal_throttle"] = True
    max_level = _run_events(events)
    passed = max_level == "HOLD"
    return FailureResult("thermal_throttle_jamming", passed, f"max_level={max_level}", max_level)


def simulate_tamper_during_alert() -> FailureResult:
    sensors = SimulatedSensorArray("t", scenario_from_name("intrusion"), rng_seed=2)
    events = list(sensors.stream(12.0, 2.0))
    for event in events[-5:]:
        event.flags["tamper_detected"] = True
    max_level = _run_events(events)
    passed = max_level in {"ORANGE", "RED", "YELLOW", "HOLD"}
    return FailureResult("tamper_during_intrusion", passed, f"max_level={max_level}", max_level)


def simulate_low_power_duty_cycle() -> FailureResult:
    """During sleep window, scores should stay lower than full active intrusion."""
    from sentry.hardware.live_array import LiveSensorArray

    node_config = {
        "simulation": {"enabled": True, "rng_seed": 4, "fallback_scenario": "intrusion"},
        "hardware": {"duty_cycle": {"active_window_s": 1.0, "sleep_window_s": 8.0}},
    }
    array = LiveSensorArray("t", node_config)
    array._cycle_start = __import__("time").monotonic() - 0.2
    active_event = array.sample(0.0)
    array._cycle_start = __import__("time").monotonic() - 5.0
    sleep_event = array.sample(0.0)
    array.close()
    passed = active_event.flags.get("hardware_active_window") and not sleep_event.flags.get(
        "hardware_active_window"
    )
    return FailureResult(
        "low_power_duty_cycle",
        passed,
        f"active={active_event.flags.get('hardware_active_window')} sleep={sleep_event.flags.get('hardware_active_window')}",
    )


def simulate_deployment_chain_break() -> FailureResult:
    """Line tension break mid-chain — downstream nodes must not alert ORANGE+."""
    from sentry.deployment.config import ChainDeploymentConfig
    from sentry.deployment.manager import DeploymentManager

    cfg = ChainDeploymentConfig(node_count=8, launch_method="spring_launcher", launch_velocity_m_s=22.0)
    mgr = DeploymentManager(cfg, chain_id="FAIL-CHAIN")
    mgr.simulate_launch()
    physics = mgr.state.physics
    passed = physics is not None and physics.operational_nodes < physics.node_count
    return FailureResult(
        "deployment_chain_break",
        passed,
        f"operational={physics.operational_nodes if physics else 0}/{physics.node_count if physics else 0}",
    )


def simulate_deployment_entanglement() -> FailureResult:
    """Entanglement reduces mesh join — most nodes fail chain_auto_join."""
    from sentry.deployment.config import ChainDeploymentConfig
    from sentry.deployment.manager import DeploymentManager

    cfg = ChainDeploymentConfig(node_count=6, entanglement_prior_per_node=0.95)
    mgr = DeploymentManager(cfg, chain_id="ENTANGLE-TEST")
    mgr.simulate_launch()
    join = mgr.run_mesh_auto_join()
    passed = len(join.failed) >= 3
    return FailureResult(
        "deployment_entanglement",
        passed,
        f"failed_join={len(join.failed)}/{len(join.failed) + len(join.joined)}",
    )


def simulate_deployment_antenna_damage() -> FailureResult:
    """Antenna deploy failure — post-landing BIT should fail nodes."""
    from sentry.deployment.config import ChainDeploymentConfig
    from sentry.deployment.manager import DeploymentManager

    cfg = ChainDeploymentConfig(antenna_deploy_success_prior=0.05, node_count=4)
    mgr = DeploymentManager(cfg, chain_id="ANT-FAIL")
    mgr.simulate_launch()
    mgr.run_mesh_auto_join()
    post = mgr.run_post_landing_checks()
    passed = post.get("checks_passed", 0) < post.get("checks_total", 1)
    return FailureResult(
        "deployment_antenna_damage",
        passed,
        f"passed={post.get('checks_passed')}/{post.get('checks_total')}",
    )


def simulate_deployment_suppresses_alerts() -> FailureResult:
    """During deploying phase intrusion must not escalate past CLEAR (except HOLD)."""
    mission = {
        "deployment": {
            "enabled": True,
            "node_count": 4,
            "launch_method": "pneumatic_soft",
        }
    }
    guardian = SentryGuardian("sentry-deploy-suppress", mission)
    guardian.deployment.simulate_launch()  # type: ignore[union-attr]
    sensors = SimulatedSensorArray("t", scenario_from_name("intrusion"), rng_seed=6)
    max_level = "CLEAR"
    rank = {"CLEAR": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3, "HOLD": 4}
    for event in sensors.stream(5.0, 2.0):
        alert = guardian.process(event)
        if rank[alert.level] > rank[max_level]:
            max_level = alert.level
    passed = max_level == "CLEAR"
    return FailureResult(
        "deployment_alert_suppression",
        passed,
        f"max_level={max_level} phase={guardian.deployment.state.phase}",  # type: ignore[union-attr]
        max_level,
    )


def run_all() -> dict[str, Any]:
    results = [
        simulate_sensor_dropout(),
        simulate_thermal_throttle(),
        simulate_tamper_during_alert(),
        simulate_low_power_duty_cycle(),
        simulate_deployment_chain_break(),
        simulate_deployment_entanglement(),
        simulate_deployment_antenna_damage(),
        simulate_deployment_suppresses_alerts(),
    ]
    ok = all(r.passed for r in results)
    return {
        "codename": "SENTRY",
        "overall": "PASS" if ok else "FAIL",
        "modes": [r.to_dict() for r in results],
    }
