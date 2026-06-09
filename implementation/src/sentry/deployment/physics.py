"""Line tension, impact, and spacing physics stubs (mechanical throw only)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

from sentry.deployment.config import ChainDeploymentConfig, COMPONENT_SURVIVAL_G


class LaunchMethod(str, Enum):
    """Defensive-only mechanical methods — no explosives."""

    HAND_EMPLACE = "hand_emplace"
    PNEUMATIC_SOFT = "pneumatic_soft"
    SPRING_LAUNCHER = "spring_launcher"
    LINE_CHARGE_REFERENCE = "line_charge_reference"  # model only — not recommended


LAUNCH_PEAK_G: dict[LaunchMethod, float] = {
    LaunchMethod.HAND_EMPLACE: 8.0,
    LaunchMethod.PNEUMATIC_SOFT: 35.0,
    LaunchMethod.SPRING_LAUNCHER: 55.0,
    LaunchMethod.LINE_CHARGE_REFERENCE: 450.0,
}


@dataclass
class NodeImpactResult:
    index: int
    peak_g: float
    line_tension_n: float
    spacing_m: float
    pi_survives: bool
    rtl_survives: bool
    mic_survives: bool
    battery_survives: bool
    node_operational: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "peak_g": round(self.peak_g, 2),
            "line_tension_n": round(self.line_tension_n, 2),
            "spacing_m": self.spacing_m,
            "pi_survives": self.pi_survives,
            "rtl_survives": self.rtl_survives,
            "mic_survives": self.mic_survives,
            "battery_survives": self.battery_survives,
            "node_operational": self.node_operational,
        }


@dataclass
class LinePhysicsResult:
    method: str
    node_count: int
    chain_length_m: float
    peak_g_launch: float
    max_line_tension_n: float
    operational_nodes: int
    chain_intact: bool
    nodes: list[NodeImpactResult]
    blunt_assessment: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "node_count": self.node_count,
            "chain_length_m": round(self.chain_length_m, 2),
            "peak_g_launch": self.peak_g_launch,
            "max_line_tension_n": round(self.max_line_tension_n, 2),
            "operational_nodes": self.operational_nodes,
            "chain_intact": self.chain_intact,
            "nodes": [n.to_dict() for n in self.nodes],
            "blunt_assessment": self.blunt_assessment,
        }


def line_tension_n(
    node_mass_kg: float,
    peak_g: float,
    line_angle_from_horizontal_deg: float = 15.0,
) -> float:
    """Axial line tension during deceleration (point-mass stub)."""
    g = 9.81
    angle = math.radians(line_angle_from_horizontal_deg)
    inertial = node_mass_kg * peak_g * g
    weight_component = node_mass_kg * g * math.sin(angle)
    return inertial + weight_component


def peak_g_at_node(
    launch_peak_g: float,
    node_index: int,
    node_count: int,
    velocity_m_s: float,
    spacing_m: float,
) -> float:
    """
    Impact g decreases along chain; leading nodes see full launch decel,
    trailing nodes see reduced peak from line whip damping (stub).
    """
    if node_count <= 1:
        return launch_peak_g
    whip_factor = 1.0 - 0.12 * (node_index / max(node_count - 1, 1))
    velocity_factor = min(1.0, velocity_m_s / 25.0)
    return launch_peak_g * whip_factor * (0.85 + 0.15 * velocity_factor)


def simulate_line_deployment(config: ChainDeploymentConfig | None = None) -> LinePhysicsResult:
    """
    Simulate mechanical line deployment along a connected chain.
    BLUNT: line-charge reference mode models destruction — not field recommended.
    """
    config = config or ChainDeploymentConfig()
    try:
        method = LaunchMethod(config.launch_method)
    except ValueError:
        method = LaunchMethod.PNEUMATIC_SOFT

    launch_peak = LAUNCH_PEAK_G[method]
    spacing = max(5.0, min(10.0, config.spacing_m))
    node_count = max(2, config.node_count)
    chain_length = spacing * (node_count - 1)

    nodes: list[NodeImpactResult] = []
    max_tension = 0.0
    chain_break = False

    for i in range(node_count):
        peak = peak_g_at_node(launch_peak, i, node_count, config.launch_velocity_m_s, spacing)
        tension = line_tension_n(config.node_mass_kg, peak)
        max_tension = max(max_tension, tension)

        pi_ok = peak <= COMPONENT_SURVIVAL_G["pi_zero_2w"]
        rtl_ok = peak <= COMPONENT_SURVIVAL_G["rtl_sdr_v3"]
        mic_ok = peak <= COMPONENT_SURVIVAL_G["mems_mic"]
        bat_ok = peak <= COMPONENT_SURVIVAL_G["lipo_2s"]
        node_ok = pi_ok and rtl_ok and mic_ok and bat_ok

        if tension > 1200.0 and i > 0:
            chain_break = True
            node_ok = False

        nodes.append(
            NodeImpactResult(
                index=i,
                peak_g=peak,
                line_tension_n=tension,
                spacing_m=spacing,
                pi_survives=pi_ok,
                rtl_survives=rtl_ok,
                mic_survives=mic_ok,
                battery_survives=bat_ok,
                node_operational=node_ok and not chain_break,
            )
        )
        if chain_break:
            break

    operational = sum(1 for n in nodes if n.node_operational)
    chain_intact = not chain_break and operational == node_count

    if method == LaunchMethod.LINE_CHARGE_REFERENCE:
        blunt = (
            "LINE-CHARGE REFERENCE: peak g ~450 — COTS Pi/RTL/MEMS destroyed. "
            "Not aligned with soldier-safety or cheap mandate."
        )
    elif operational < node_count:
        blunt = (
            f"Mechanical {method.value}: {operational}/{node_count} nodes operational. "
            "Ruggedization or hand-emplace required for full chain."
        )
    else:
        blunt = f"Mechanical {method.value}: full chain operational on paper — bench impact test still required."

    return LinePhysicsResult(
        method=method.value,
        node_count=node_count,
        chain_length_m=chain_length,
        peak_g_launch=launch_peak,
        max_line_tension_n=max_tension,
        operational_nodes=operational,
        chain_intact=chain_intact,
        nodes=nodes,
        blunt_assessment=blunt,
    )
