"""Tamper response — HMAC audit event + configurable secret wipe."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sentry.audit import AuditLogger

LOG = logging.getLogger("SENTRY")


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


def _scrub_env(key: str) -> bool:
    if key not in os.environ:
        return False
    value = os.environ.get(key, "")
    if value:
        os.environ[key] = "0" * len(value)
    del os.environ[key]
    return True


@dataclass
class TamperWipeConfig:
    wipe_env_keys: list[str] = field(default_factory=lambda: ["SENTRY_AUDIT_HMAC_KEY"])
    wipe_paths: list[str] = field(default_factory=lambda: [
        "/var/lib/sentry/meshtastic_spool.jsonl",
        "/etc/sentry/environment",
    ])
    dry_run: bool = True


def handle_tamper(
    audit: AuditLogger,
    config: TamperWipeConfig | None = None,
    timestamp_s: float | None = None,
) -> dict[str, Any]:
    """Log tamper to audit chain and wipe sensitive material (dry-run by default)."""
    cfg = config or TamperWipeConfig()
    entry = audit.append(
        "tamper_wipe",
        {"action": "tamper_detected", "dry_run": cfg.dry_run},
        timestamp_s=timestamp_s,
    )
    wiped: list[str] = []

    if cfg.dry_run:
        LOG.warning("SENTRY tamper dry-run — would wipe secrets")
        return {"audit_entry": entry, "wiped": wiped, "dry_run": True}

    audit.wipe_secret()
    for key in cfg.wipe_env_keys:
        if _scrub_env(key):
            wiped.append(f"env:{key}")

    for raw in cfg.wipe_paths:
        path = Path(raw)
        try:
            if path.is_file():
                _zero_fill(path)
                path.unlink(missing_ok=True)
                wiped.append(str(path))
        except OSError as exc:
            LOG.error("SENTRY tamper wipe failed for %s: %s", path, exc)

    return {"audit_entry": entry, "wiped": wiped, "dry_run": False}
