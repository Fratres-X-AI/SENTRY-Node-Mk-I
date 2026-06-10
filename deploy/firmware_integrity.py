#!/usr/bin/env python3
"""SENTRY-DARKSPACE firmware and memory integrity shield."""

from __future__ import annotations

import ctypes
import hashlib
import os
import sys
from pathlib import Path


REPO_ROOT = Path(os.environ.get("SENTRY_REPO", "/opt/sentry-node-mk-i"))

GOLDEN_MANIFEST = {
    "implementation/src/sentry/sensors/rf_sensor.py": "7f9c2497fb04645d9d5ded260d9e011122be3608bf32c85432ad04e6e7ca1c46",
    "implementation/src/sentry/sensors/acoustic_sensor.py": "56190ea8e956c1e300829e46f1ddc1581f7fb6f21aee19728ef42672a7f06bbb",
    "implementation/src/sentry/sensors/ghost_monitor.py": "1e5330611708e8bd1e20f218718c0c68a964274cb9d4acf6676d4d9bc7c8e683",
    "implementation/src/sentry/sensors/whisper_detector.py": "f168fe57162b21fa3e213d0e35299c763686f2883260eeffeb458c01b22ee743",
    "implementation/src/sentry/scoring.py": "ea3c77daa117b06d6746b8b9f79ffbd798b6c07e67d6f736a35a603f918b65f3",
    "implementation/src/sentry/networking/meshtastic_handler.py": "7f44c9017662904be4aab3054ada15a9e51f14a31569ae06355a1bb916e705d1",
    "implementation/src/sentry/networking/p2p_mesh.py": "d54091f91116cc82e5cf689a9a189103cc04c1897f39f7507a262ef08ae8dcc0",
    "implementation/src/sentry/audit/hmac_chain.py": "25abb914a7af136ba475ecfbaaf21e646849c848eadf39e0122deecd4b2ac39a",
    "implementation/src/sentry/audit/sqlite_store.py": "fe09234d231ac7e9a59d20868529ccf9809faefd70fac7e23025ca009e0dcd96",
}

WIPE_TARGETS = [
    "/etc/sentry/environment",
    "/var/lib/sentry/audit_log.db",
    "/var/lib/sentry/meshtastic_spool.jsonl",
]


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_codebase_integrity() -> None:
    if not GOLDEN_MANIFEST:
        print("[INTEGRITY] Golden manifest is empty; run scripts/generate_manifest.py before deploy.")
        trigger_emergency_wipe()
    for rel_path, golden_hash in GOLDEN_MANIFEST.items():
        path = REPO_ROOT / rel_path
        if not path.exists():
            print(f"[INTEGRITY] CRITICAL: missing code file {rel_path}")
            trigger_emergency_wipe()
        current_hash = _sha256(path)
        if current_hash != golden_hash:
            print(f"[INTEGRITY] CRITICAL: tamper detected on {rel_path}")
            print(f"[INTEGRITY] expected={golden_hash[:12]} current={current_hash[:12]}")
            trigger_emergency_wipe()
    print("[INTEGRITY] Core hashes match golden manifest.")


def lock_process_memory() -> None:
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        mcl_current = 1
        mcl_future = 2
        if libc.mlockall(mcl_current | mcl_future) == 0:
            print("[MEM_LOCK] Process memory locked.")
        else:
            errno = ctypes.get_errno()
            print(f"[MEM_LOCK] Non-fatal mlockall failure errno={errno}.")
    except Exception as exc:
        print(f"[MEM_LOCK] Non-fatal mlockall exception: {exc}")


def _zero_fill(path: Path) -> None:
    size = path.stat().st_size
    with path.open("r+b") as fh:
        remaining = size
        chunk = b"\x00" * 8192
        while remaining > 0:
            n = min(remaining, len(chunk))
            fh.write(chunk[:n])
            remaining -= n
        fh.flush()
        os.fsync(fh.fileno())


def trigger_emergency_wipe() -> None:
    print("[INTEGRITY] Emergency tamper trigger. Starting crypto wipe.")
    for raw in WIPE_TARGETS:
        path = Path(raw)
        if path.exists() and path.is_file():
            try:
                _zero_fill(path)
                path.unlink()
                print(f"[INTEGRITY] purged {raw}")
            except OSError as exc:
                print(f"[INTEGRITY] wipe failed for {raw}: {exc}")
    sys.exit(1)


def main() -> int:
    verify_codebase_integrity()
    lock_process_memory()
    return 0


if __name__ == "__main__":
    sys.exit(main())
