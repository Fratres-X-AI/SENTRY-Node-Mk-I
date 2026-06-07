"""Immutable HMAC hash-chain audit logger."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any


GENESIS_HASH = "0" * 64


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass
class AuditLogger:
    """Append-only audit chain for SENTRY defensive events."""

    secret: str = field(default_factory=lambda: os.environ.get("SENTRY_AUDIT_HMAC_KEY", "sentry-dev-key"))
    _seq: int = 0
    _prev_hash: str = GENESIS_HASH

    def append(self, event: str, payload: dict[str, Any], timestamp_s: float | None = None) -> dict[str, Any]:
        ts = time.time() if timestamp_s is None else timestamp_s
        payload_hash = _sha256_hex(_canonical_json(payload))
        body = f"{self._seq}|{ts}|{event}|{payload_hash}|{self._prev_hash}"
        entry_hash = hmac.new(self.secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()

        entry = {
            "schema": "audit_entry.v1",
            "codename": "SENTRY",
            "seq": self._seq,
            "timestamp_s": ts,
            "event": event,
            "payload_hash": payload_hash,
            "prev_hash": self._prev_hash,
            "entry_hash": entry_hash,
        }
        self._seq += 1
        self._prev_hash = entry_hash
        return entry

    def verify_chain(self, entries: list[dict[str, Any]]) -> bool:
        prev = GENESIS_HASH
        for i, entry in enumerate(entries):
            if entry.get("seq") != i:
                return False
            if entry.get("prev_hash") != prev:
                return False
            body = (
                f"{entry['seq']}|{entry['timestamp_s']}|{entry['event']}|"
                f"{entry['payload_hash']}|{entry['prev_hash']}"
            )
            expected = hmac.new(
                self.secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            if entry.get("entry_hash") != expected:
                return False
            prev = entry["entry_hash"]
        return True
