#!/usr/bin/env python3
"""Generate the firmware integrity golden manifest."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCKDOWN_SCRIPT_PATH = ROOT / "deploy" / "firmware_integrity.py"

TARGET_FILES = [
    "implementation/src/sentry/sensors/rf_sensor.py",
    "implementation/src/sentry/sensors/acoustic_sensor.py",
    "implementation/src/sentry/sensors/ghost_monitor.py",
    "implementation/src/sentry/sensors/whisper_detector.py",
    "implementation/src/sentry/scoring.py",
    "implementation/src/sentry/networking/meshtastic_handler.py",
    "implementation/src/sentry/networking/p2p_mesh.py",
    "implementation/src/sentry/audit/hmac_chain.py",
    "implementation/src/sentry/audit/sqlite_store.py",
]


def calculate_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def update_manifest_file() -> None:
    manifest_lines = []
    for rel_path in TARGET_FILES:
        path = ROOT / rel_path
        if not path.exists():
            raise FileNotFoundError(rel_path)
        manifest_lines.append(f'    "{rel_path}": "{calculate_sha256(path)}",')

    content = LOCKDOWN_SCRIPT_PATH.read_text(encoding="utf-8")
    start_marker = "GOLDEN_MANIFEST = {"
    start_idx = content.index(start_marker) + len(start_marker)
    end_idx = content.index("}", start_idx)
    new_manifest = "\n" + "\n".join(manifest_lines) + "\n"
    LOCKDOWN_SCRIPT_PATH.write_text(content[:start_idx] + new_manifest + content[end_idx:], encoding="utf-8")


if __name__ == "__main__":
    update_manifest_file()
    print("Updated deploy/firmware_integrity.py")
