"""Friis transmission equation helpers for passive RF range modeling."""

from __future__ import annotations

import math


def friis_received_power_dbm(
    tx_power_dbm: float,
    tx_gain_dbi: float,
    rx_gain_dbi: float,
    distance_m: float,
    frequency_hz: float,
) -> float:
    """Free-space path loss (Friis) received power estimate."""
    if distance_m <= 0:
        raise ValueError("distance_m must be positive")
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be positive")
    wavelength_m = 299_792_458.0 / frequency_hz
    fspl_db = 20.0 * math.log10(4.0 * math.pi * distance_m / wavelength_m)
    return tx_power_dbm + tx_gain_dbi + rx_gain_dbi - fspl_db


def friis_max_range_m(
    tx_power_dbm: float,
    tx_gain_dbi: float,
    rx_gain_dbi: float,
    rx_sensitivity_dbm: float,
    frequency_hz: float,
) -> float:
    """Solve Friis for max range given receiver sensitivity."""
    wavelength_m = 299_792_458.0 / frequency_hz
    max_path_loss = tx_power_dbm + tx_gain_dbi + rx_gain_dbi - rx_sensitivity_dbm
    exponent = max_path_loss / 20.0
    return float(wavelength_m / (4.0 * math.pi) * (10.0**exponent))


def rtl_power_anomaly_score(
    power_dbm_values: list[float],
    baseline_dbm: float | None = None,
    jamming_delta_db: float = 12.0,
) -> tuple[float, bool]:
    """
    Map rtl_power sweep to normalized score and jamming flag.
    High uniform uplift across bins suggests wideband interference.
    """
    if not power_dbm_values:
        return 0.0, False
    peak = max(power_dbm_values)
    floor = min(power_dbm_values)
    mean = sum(power_dbm_values) / len(power_dbm_values)
    base = baseline_dbm if baseline_dbm is not None else floor
    delta = peak - base
    spread = peak - floor
    score = min(1.0, max(0.0, delta / max(jamming_delta_db, 1e-6)))
    jamming = spread < 3.0 and delta > jamming_delta_db * 0.6
    if mean > base + jamming_delta_db * 0.4 and spread < 4.0:
        jamming = True
    return score, jamming
