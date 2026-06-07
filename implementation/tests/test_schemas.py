from __future__ import annotations

import pytest

from sentry.schema_validate import validate


@pytest.mark.parametrize(
    "schema_name,instance",
    [
        (
            "sensor_event.v1.json",
            {
                "schema": "sensor_event.v1",
                "codename": "SENTRY",
                "node_id": "sentry-pi-001",
                "seq": 0,
                "timestamp_s": 1.0,
                "channels": {"pir": 0.1, "acoustic": 0.2, "rf": 0.0, "visual": 0.15},
                "flags": {"jamming_suspected": False, "low_visibility": False},
            },
        ),
        (
            "alert_frame.v1.json",
            {
                "schema": "alert_frame.v1",
                "codename": "SENTRY",
                "node_id": "sentry-pi-001",
                "seq": 0,
                "timestamp_s": 1.0,
                "level": "YELLOW",
                "threat_score": 0.4,
                "rationale": "test",
                "guardian_state": "watch",
                "sensor_event": {},
            },
        ),
    ],
)
def test_schema_validation(schema_name: str, instance: dict) -> None:
    validate(instance, schema_name)
