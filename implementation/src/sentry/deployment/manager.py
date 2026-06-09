"""Deployment lifecycle manager — integrates with SentryGuardian."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sentry.deployment.chain_topology import (
    ChainJoinResult,
    ChainTopology,
    build_chain_topology,
    mesh_peer_list,
    simulate_mesh_auto_join,
)
from sentry.deployment.config import ChainDeploymentConfig
from sentry.deployment.physics import LinePhysicsResult, simulate_line_deployment
from sentry.deployment.post_landing import run_chain_post_landing


# Guardian-visible deployment phases (before operational watch FSM)
DEPLOYMENT_PHASES = (
    "stowed",
    "deploying",
    "deployed",
    "chain_joining",
    "operational",
)


@dataclass
class DeploymentState:
    phase: str = "stowed"
    chain_id: str = ""
    physics: LinePhysicsResult | None = None
    topology: ChainTopology | None = None
    join_result: ChainJoinResult | None = None
    post_landing: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "chain_id": self.chain_id,
            "physics": self.physics.to_dict() if self.physics else None,
            "topology": self.topology.to_dict() if self.topology else None,
            "join_result": self.join_result.to_dict() if self.join_result else None,
            "post_landing": self.post_landing,
        }


class DeploymentManager:
    """Mechanical line chain deployment — no explosives."""

    def __init__(self, config: ChainDeploymentConfig | None = None, chain_id: str = "CHAIN-ALPHA") -> None:
        self.config = config or ChainDeploymentConfig()
        self.chain_id = chain_id
        self.state = DeploymentState()

    @classmethod
    def from_mission(cls, mission: dict[str, Any] | None) -> DeploymentManager | None:
        mission = mission or {}
        dep = mission.get("deployment")
        if not dep or not dep.get("enabled"):
            return None
        return cls(
            config=ChainDeploymentConfig.from_dict(dep),
            chain_id=str(dep.get("chain_id", "CHAIN-ALPHA")),
        )

    def simulate_launch(self) -> DeploymentState:
        """Run line physics and advance to deployed phase."""
        self.state.phase = "deploying"
        physics = simulate_line_deployment(self.config)
        self.state.physics = physics
        self.state.topology = build_chain_topology(
            self.chain_id,
            physics,
            self.config.spacing_m,
        )
        self.state.phase = "deployed"
        return self.state

    def run_mesh_auto_join(self) -> ChainJoinResult:
        """Simulate Meshtastic auto-join along chain."""
        if self.state.topology is None:
            raise RuntimeError("Run simulate_launch first")
        self.state.phase = "chain_joining"
        join = simulate_mesh_auto_join(self.state.topology, self.config)
        self.state.join_result = join
        return join

    def run_post_landing_checks(self) -> dict[str, Any]:
        if self.state.topology is None:
            raise RuntimeError("Run simulate_launch first")
        report = run_chain_post_landing(self.state.topology, self.config)
        self.state.post_landing = report
        if report.get("checks_passed", 0) > 0:
            self.state.phase = "operational"
        return report

    def full_deploy_sequence(self) -> dict[str, Any]:
        """Launch → mesh join → post-landing BIT."""
        self.simulate_launch()
        join = self.run_mesh_auto_join()
        post = self.run_post_landing_checks()
        return {
            "codename": "SENTRY",
            "chain_id": self.chain_id,
            "deployment_state": self.state.to_dict(),
            "mesh_joined": len(join.joined),
            "post_landing_pass": post.get("checks_passed", 0),
            "operational": self.state.phase == "operational",
        }

    def mesh_peers_for(self, node_id: str) -> list[str]:
        if self.state.topology is None:
            return []
        return mesh_peer_list(self.state.topology, node_id)

    def alerts_suppressed(self) -> bool:
        """Threat alerts suppressed until operational (tamper HOLD still allowed)."""
        return self.state.phase in {"stowed", "deploying", "deployed", "chain_joining"}

    def guardian_state_label(self) -> str:
        return self.state.phase if self.alerts_suppressed() else "watch"
