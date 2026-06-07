"""Tamper response — HMAC audit event + configurable secret wipe."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sentry.audit import AuditLogger

LOG = logging.getLogger("SENTRY")


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

    for key in cfg.wipe_env_keys:
        if key in os.environ:
            del os.environ[key]
            wiped.append(f"env:{key}")

    for raw in cfg.wipe_paths:
        path = Path(raw)
        try:
            if path.is_file():
                path.write_bytes(b"\x00" * min(path.stat().st_size, 4096))
                path.unlink(missing_ok=True)
                wiped.append(str(path))
        except OSError as exc:
            LOG.error("SENTRY tamper wipe failed for %s: %s", path, exc)

    return {"audit_entry": entry, "wiped": wiped, "dry_run": False}
