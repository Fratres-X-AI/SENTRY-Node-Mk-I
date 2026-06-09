"""Deployment chain configuration defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ChainDeploymentConfig:
    """Mechanical line-thrower chain — defensive emplacement only."""

    node_count: int = 8
    spacing_m: float = 7.5
    node_mass_kg: float = 0.25
    line_diameter_mm: float = 3.0
    launch_method: str = "pneumatic_soft"
    launch_velocity_m_s: float = 18.0
    landing_angle_deg_std: float = 12.0
    antenna_deploy_success_prior: float = 0.72
    entanglement_prior_per_node: float = 0.08
    require_post_landing_check: bool = True
    mesh_auto_join_timeout_s: float = 45.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ChainDeploymentConfig:
        data = data or {}
        return cls(
            node_count=int(data.get("node_count", 8)),
            spacing_m=float(data.get("spacing_m", 7.5)),
            node_mass_kg=float(data.get("node_mass_kg", 0.25)),
            line_diameter_mm=float(data.get("line_diameter_mm", 3.0)),
            launch_method=str(data.get("launch_method", "pneumatic_soft")),
            launch_velocity_m_s=float(data.get("launch_velocity_m_s", 18.0)),
            landing_angle_deg_std=float(data.get("landing_angle_deg_std", 12.0)),
            antenna_deploy_success_prior=float(data.get("antenna_deploy_success_prior", 0.72)),
            entanglement_prior_per_node=float(data.get("entanglement_prior_per_node", 0.08)),
            require_post_landing_check=bool(data.get("require_post_landing_check", True)),
            mesh_auto_join_timeout_s=float(data.get("mesh_auto_join_timeout_s", 45.0)),
        )


# COTS survival thresholds (paper — bench validation required)
COMPONENT_SURVIVAL_G: dict[str, float] = {
    "pi_zero_2w": 40.0,
    "rtl_sdr_v3": 25.0,
    "mems_mic": 30.0,
    "lipo_2s": 60.0,
    "meshtastic_radio": 35.0,
    "enclosure_abs": 80.0,
}
