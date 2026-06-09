"""Deployment chain physics and guardian integration tests."""

from __future__ import annotations

from sentry.deployment.config import ChainDeploymentConfig
from sentry.deployment.manager import DeploymentManager
from sentry.deployment.physics import LaunchMethod, simulate_line_deployment
from sentry.guardian import SentryGuardian
from sentry.simulation.synthetic import SimulatedSensorArray, scenario_from_name


def test_pneumatic_physics_partial_survival() -> None:
    r = simulate_line_deployment(
        ChainDeploymentConfig(node_count=8, launch_method="pneumatic_soft")
    )
    assert r.node_count == 8
    # 35g exceeds RTL-SDR 25g COTS limit — partial/no full chain without ruggedization
    assert r.operational_nodes < r.node_count
    assert any(n.pi_survives for n in r.nodes)


def test_line_charge_reference_destroys_chain() -> None:
    r = simulate_line_deployment(
        ChainDeploymentConfig(node_count=4, launch_method="line_charge_reference")
    )
    assert r.operational_nodes == 0
    assert "LINE-CHARGE" in r.blunt_assessment


def test_deployment_manager_sequence() -> None:
    mgr = DeploymentManager(ChainDeploymentConfig(node_count=4), "TEST-CHAIN")
    out = mgr.full_deploy_sequence()
    assert "deployment_state" in out
    assert mgr.state.phase in {"operational", "chain_joining", "deployed"}


def test_guardian_suppresses_during_deploy() -> None:
    mission = {"deployment": {"enabled": True, "node_count": 4, "launch_method": "hand_emplace"}}
    g = SentryGuardian("n1", mission)
    g.deployment.simulate_launch()  # type: ignore[union-attr]
    sensors = SimulatedSensorArray("n1", scenario_from_name("intrusion"), rng_seed=1)
    alert = next(iter(g.process(e) for e in sensors.stream(1.0, 2.0)))
    assert alert.level == "CLEAR"
    assert alert.guardian_state == "deployed"


def test_monte_carlo_cpu() -> None:
    from sentry.deployment.monte_carlo_impact import gpu_monte_carlo_deployment

    r = gpu_monte_carlo_deployment(
        total=1000,
        config=ChainDeploymentConfig(node_count=6, launch_method="pneumatic_soft"),
    )
    assert r.total_scenarios == 1000
    assert 0.0 <= r.full_chain_survival_rate <= 1.0


def test_spacing_clamped_5_to_10m() -> None:
    r = simulate_line_deployment(ChainDeploymentConfig(spacing_m=20.0, node_count=3))
    assert r.nodes[0].spacing_m == 10.0
