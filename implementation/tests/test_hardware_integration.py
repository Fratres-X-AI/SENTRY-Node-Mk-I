from __future__ import annotations

import math

from sentry.failure_modes import run_all
from sentry.hardware.live_array import LiveSensorArray
from sentry.hardware.probe import probe_all
from sentry.sensors.acoustic_sensor import AcousticSensorConfig, generate_synthetic_tone, _fft_peaks
from sentry.sensors.power_metrics import PowerMetrics
from sentry.sensors.rf_sensor import RfSensor


def test_hardware_probe_runs() -> None:
    report = probe_all({"hardware": {"profile": "test"}, "node_id": "t1"})
    assert report["codename"] == "SENTRY"
    assert report["total_count"] == 6
    assert "known_gaps" in report


def test_live_array_fallback_on_desktop() -> None:
    cfg = {
        "simulation": {"fallback_scenario": "benign", "rng_seed": 1},
        "hardware": {},
        "node_id": "sentry-test",
    }
    array = LiveSensorArray("sentry-test", cfg)
    event = array.sample(0.0)
    array.close()
    assert event.to_dict()["schema"] == "sensor_event.v1"
    assert event.flags["fallback_channels"]["rf"] is True


def test_power_metrics_desktop() -> None:
    pm = PowerMetrics()
    s = pm.record(duty_active=True, rtl_active=True)
    assert s.source == "desktop_simulation"
    summary = pm.summary()
    assert summary["samples"] == 1
    assert "under_target" in summary


def test_acoustic_scipy_propeller_peak() -> None:
    cfg = AcousticSensorConfig()
    samples = generate_synthetic_tone(220.0, cfg.sample_rate_hz, cfg.frame_samples)
    result = _fft_peaks(samples, cfg.sample_rate_hz, cfg)
    assert result.score > 0.2
    assert result.propeller_peak is True


def test_rf_sensor_synthetic_read() -> None:
    rf = RfSensor()
    result = rf.read(synthetic_rf=0.9, synthetic_jamming=True)
    assert result.score > 0.0
    assert result.jamming is True
    friis = rf.friis_note(500.0)
    assert friis["estimated_rx_dbm_2g4"] < 0


def test_failure_modes_suite_passes() -> None:
    report = run_all()
    assert report["overall"] == "PASS"
