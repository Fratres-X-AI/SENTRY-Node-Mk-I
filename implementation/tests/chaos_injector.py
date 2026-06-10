#!/usr/bin/env python3
"""Compatibility wrapper for the root chaos injector."""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
runpy.run_path(str(ROOT / "tests" / "chaos_injector.py"), run_name="__main__")
