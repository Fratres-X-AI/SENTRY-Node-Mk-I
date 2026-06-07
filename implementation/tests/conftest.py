"""Pytest hooks for SENTRY GPU validation on RunPod."""

from __future__ import annotations

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--gpu",
        action="store_true",
        default=False,
        help="Force CUDA workloads (RunPod dev only; Pi field is CPU-only)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "gpu: requires CUDA (RunPod simulation)")


@pytest.fixture
def sentry_gpu(request: pytest.FixtureRequest):
    """Enable SENTRY_FORCE_GPU when --gpu passed."""
    if request.config.getoption("--gpu"):
        os.environ["SENTRY_FORCE_GPU"] = "1"
    return request.config.getoption("--gpu")
