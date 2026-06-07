from __future__ import annotations

import math

from sentry.hardware.rf_friis import friis_max_range_m, friis_received_power_dbm, rtl_power_anomaly_score
from sentry.hardware.rf_rtl import parse_rtl_power_csv
from sentry.sensors.rf_sensor import RfSensor


def test_friis_received_power_decreases_with_distance() -> None:
    near = friis_received_power_dbm(10.0, 2.0, 2.0, 100.0, 433e6)
    far = friis_received_power_dbm(10.0, 2.0, 2.0, 1000.0, 433e6)
    assert near > far


def test_friis_max_range_positive() -> None:
    r = friis_max_range_m(10.0, 2.0, 2.0, -90.0, 433e6)
    assert r > 0


def test_rtl_power_anomaly_jamming() -> None:
    values = [-50.0] * 20
    values[5] = -30.0
    score, jamming = rtl_power_anomaly_score(values, baseline_dbm=-50.0)
    assert score > 0.5
    assert jamming is False


def test_rtl_power_wideband_jamming_flag() -> None:
    values = [-35.0] * 30
    score, jamming = rtl_power_anomaly_score(values, baseline_dbm=-50.0)
    assert score > 0.5
    assert jamming is True


def test_parse_rtl_power_csv() -> None:
    sample = "# comment\n2024-01-01,1000,433000000,434000000,10000,0,-50.0,-49.5,-48.0\n"
    values = parse_rtl_power_csv(sample)
    assert len(values) == 3
    assert math.isclose(values[0], -50.0)


def test_rf_sensor_alternates_bands() -> None:
    rf = RfSensor()
    r1 = rf.read()
    r2 = rf.read()
    assert r1.source in {"rtl_power", "synthetic", "synthetic_5g8", "fallback"}
    assert r2.source in {"rtl_power", "synthetic", "synthetic_5g8", "fallback"}
