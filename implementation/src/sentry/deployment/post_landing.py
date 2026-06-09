"""Post-landing self-check — antenna, tamper, power, mesh readiness."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from sentry.deployment.chain_topology import ChainTopology
from sentry.deployment.config import ChainDeploymentConfig


@dataclass
class PostLandingCheck:
    node_id: str
    power_ok: bool
    tamper_intact: bool
    antenna_deployed: bool
    sensors_responsive: bool
    mesh_ready: bool
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "power_ok": self.power_ok,
            "tamper_intact": self.tamper_intact,
            "antenna_deployed": self.antenna_deployed,
            "sensors_responsive": self.sensors_responsive,
            "mesh_ready": self.mesh_ready,
            "passed": self.passed,
            "detail": self.detail,
        }


def run_post_landing_check(
    node_id: str,
    operational: bool,
    mesh_joined: bool,
    config: ChainDeploymentConfig | None = None,
    rng: random.Random | None = None,
) -> PostLandingCheck:
    """Simulate post-landing BIT for one chain node."""
    config = config or ChainDeploymentConfig()
    rng = rng or random.Random(hash(node_id) & 0xFFFF)

    if not operational:
        return PostLandingCheck(
            node_id=node_id,
            power_ok=False,
            tamper_intact=False,
            antenna_deployed=False,
            sensors_responsive=False,
            mesh_ready=False,
            passed=False,
            detail="Node failed impact — skip BIT",
        )

    battery_rupture = rng.random() < 0.04
    power_ok = not battery_rupture and rng.random() > 0.05
    tamper_intact = rng.random() > 0.03
    antenna_deployed = rng.random() < config.antenna_deploy_success_prior
    sensors_responsive = power_ok and rng.random() > 0.08
    mesh_ready = mesh_joined and antenna_deployed and power_ok

    passed = all([power_ok, tamper_intact, antenna_deployed, sensors_responsive, mesh_ready])
    detail = "POST_LANDING_PASS" if passed else "POST_LANDING_FAIL — hold-safe until manual verify"

    return PostLandingCheck(
        node_id=node_id,
        power_ok=power_ok,
        tamper_intact=tamper_intact,
        antenna_deployed=antenna_deployed,
        sensors_responsive=sensors_responsive,
        mesh_ready=mesh_ready,
        passed=passed,
        detail=detail,
    )


def run_chain_post_landing(
    topology: ChainTopology,
    config: ChainDeploymentConfig | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Run post-landing checks on all operational chain nodes."""
    config = config or ChainDeploymentConfig()
    rng = rng or random.Random(7)
    checks: list[PostLandingCheck] = []
    for node in topology.nodes:
        checks.append(
            run_post_landing_check(
                node.node_id,
                node.operational,
                node.mesh_joined,
                config=config,
                rng=rng,
            )
        )
    passed = sum(1 for c in checks if c.passed)
    return {
        "codename": "SENTRY",
        "chain_id": topology.chain_id,
        "checks_passed": passed,
        "checks_total": len(checks),
        "all_pass": passed == len(checks) and passed > 0,
        "checks": [c.to_dict() for c in checks],
    }
