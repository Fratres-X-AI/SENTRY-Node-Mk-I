"""Connected-chain topology and mesh auto-join simulation."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from sentry.deployment.config import ChainDeploymentConfig
from sentry.deployment.physics import LinePhysicsResult, NodeImpactResult


@dataclass
class ChainNode:
    node_id: str
    chain_index: int
    offset_m: float
    role: str
    upstream_id: str | None
    downstream_id: str | None
    operational: bool
    mesh_joined: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "chain_index": self.chain_index,
            "offset_m": round(self.offset_m, 2),
            "role": self.role,
            "upstream_id": self.upstream_id,
            "downstream_id": self.downstream_id,
            "operational": self.operational,
            "mesh_joined": self.mesh_joined,
        }


@dataclass
class ChainTopology:
    chain_id: str
    spacing_m: float
    nodes: list[ChainNode] = field(default_factory=list)

    @property
    def operational_count(self) -> int:
        return sum(1 for n in self.nodes if n.operational)

    @property
    def mesh_joined_count(self) -> int:
        return sum(1 for n in self.nodes if n.mesh_joined)

    @property
    def chain_connected(self) -> bool:
        """True if every operational segment has upstream/downstream links intact."""
        ops = [n for n in self.nodes if n.operational]
        if len(ops) < 2:
            return len(ops) == 1
        for node in ops:
            if node.chain_index > 0 and node.upstream_id is None:
                return False
            if node.chain_index < len(self.nodes) - 1 and node.downstream_id is None:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "spacing_m": self.spacing_m,
            "operational_count": self.operational_count,
            "mesh_joined_count": self.mesh_joined_count,
            "chain_connected": self.chain_connected,
            "nodes": [n.to_dict() for n in self.nodes],
        }


@dataclass
class ChainJoinResult:
    joined: list[str]
    failed: list[str]
    timeout_s: float
    topology: ChainTopology

    def to_dict(self) -> dict[str, Any]:
        return {
            "joined": self.joined,
            "failed": self.failed,
            "timeout_s": self.timeout_s,
            "topology": self.topology.to_dict(),
        }


def build_chain_topology(
    chain_id: str,
    physics: LinePhysicsResult,
    spacing_m: float,
    prefix: str = "sentry-chain",
) -> ChainTopology:
    """Build linear chain from physics impact results."""
    nodes: list[ChainNode] = []
    for nr in physics.nodes:
        if isinstance(nr, NodeImpactResult):
            impact = nr
        else:
            continue
        nid = f"{prefix}-{impact.index:03d}"
        role = "anchor" if impact.index == 0 else "relay" if impact.index < len(physics.nodes) - 1 else "tail"
        nodes.append(
            ChainNode(
                node_id=nid,
                chain_index=impact.index,
                offset_m=impact.index * spacing_m,
                role=role,
                upstream_id=f"{prefix}-{impact.index - 1:03d}" if impact.index > 0 else None,
                downstream_id=f"{prefix}-{impact.index + 1:03d}" if impact.index < len(physics.nodes) - 1 else None,
                operational=impact.node_operational,
            )
        )
    return ChainTopology(chain_id=chain_id, spacing_m=spacing_m, nodes=nodes)


def simulate_mesh_auto_join(
    topology: ChainTopology,
    config: ChainDeploymentConfig | None = None,
    rng: random.Random | None = None,
) -> ChainJoinResult:
    """
    Simulate Meshtastic auto-join along chain after landing.
    Antenna orientation and entanglement reduce join success per node.
    """
    config = config or ChainDeploymentConfig()
    rng = rng or random.Random(42)
    joined: list[str] = []
    failed: list[str] = []

    for node in topology.nodes:
        if not node.operational:
            failed.append(node.node_id)
            continue
        entangle = rng.random() < config.entanglement_prior_per_node
        antenna_ok = rng.random() < config.antenna_deploy_success_prior
        if entangle or not antenna_ok:
            node.mesh_joined = False
            failed.append(node.node_id)
        else:
            node.mesh_joined = True
            joined.append(node.node_id)

    return ChainJoinResult(
        joined=joined,
        failed=failed,
        timeout_s=config.mesh_auto_join_timeout_s,
        topology=topology,
    )


def mesh_peer_list(topology: ChainTopology, local_node_id: str) -> list[str]:
    """Peers for auto-join: upstream + downstream operational nodes."""
    peers: list[str] = []
    for node in topology.nodes:
        if node.node_id == local_node_id:
            if node.upstream_id:
                peers.append(node.upstream_id)
            if node.downstream_id:
                peers.append(node.downstream_id)
            break
    return peers
