from __future__ import annotations

import pytest

from sentry.audit import AuditLogger, GENESIS_HASH
from sentry.fusion import SensorFusion
from sentry.guardian import SentryGuardian
from sentry.scoring import ThreatScorer, ThreatThresholds
from sentry.simulation.synthetic import SimulatedSensorArray, scenario_from_name
from sentry.types import SensorChannels, SensorEvent


def test_sensor_event_schema_fields() -> None:
    sensors = SimulatedSensorArray("sentry-pi-test", scenario_from_name("benign"))
    event = sensors.sample(0.0)
    d = event.to_dict()
    assert d["schema"] == "sensor_event.v1"
    assert d["codename"] == "SENTRY"
    assert set(d["channels"]) == {"pir", "acoustic", "rf", "visual"}


def test_fusion_weighted_score() -> None:
    fusion = SensorFusion()
    event = SensorEvent(
        node_id="n1",
        seq=0,
        timestamp_s=0.0,
        channels=SensorChannels(pir=1.0, acoustic=0.0, rf=0.0, visual=0.0),
    )
    out = fusion.fuse(event)
    assert out["fused_score"] == pytest.approx(0.30, abs=0.01)


def test_scoring_levels() -> None:
    scorer = ThreatScorer()
    thresholds = ThreatThresholds()
    clear = scorer.score({"fused_score": 0.1, "flags": {}}, thresholds)
    assert clear["level"] == "CLEAR"
    red = scorer.score({"fused_score": 0.8, "flags": {}}, thresholds)
    assert red["level"] == "RED"
    hold = scorer.score({"fused_score": 0.6, "flags": {"jamming_suspected": True}}, thresholds)
    assert hold["level"] == "HOLD"


def test_audit_chain_integrity() -> None:
    audit = AuditLogger(secret="test-secret")
    e1 = audit.append("boot", {"codename": "SENTRY"})
    e2 = audit.append("alert", {"level": "YELLOW"})
    assert e1["prev_hash"] == GENESIS_HASH
    assert e2["prev_hash"] == e1["entry_hash"]
    assert audit.verify_chain([e1, e2])


def test_intrusion_simulation_escalates() -> None:
    guardian = SentryGuardian("sentry-pi-test", {})
    sensors = SimulatedSensorArray("sentry-pi-test", scenario_from_name("intrusion"), rng_seed=7)
    levels: set[str] = set()
    for event in sensors.stream(duration_s=20.0, rate_hz=2.0):
        alert = guardian.process(event)
        levels.add(alert.level)
    assert "YELLOW" in levels or "ORANGE" in levels or "RED" in levels


def test_jamming_hold_safe() -> None:
    guardian = SentryGuardian("sentry-pi-test", {})
    sensors = SimulatedSensorArray("sentry-pi-test", scenario_from_name("jamming"), rng_seed=7)
    saw_hold = False
    for event in sensors.stream(duration_s=20.0, rate_hz=2.0):
        alert = guardian.process(event)
        if alert.level == "HOLD":
            saw_hold = True
    assert saw_hold
