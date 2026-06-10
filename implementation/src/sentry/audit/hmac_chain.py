"""Immutable HMAC hash-chain audit logger."""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


GENESIS_HASH = "0" * 64
_DEV_SECRET = "sentry-dev-key"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _production_mode() -> bool:
    return os.environ.get("SENTRY_ENV", "").strip().lower() in {"prod", "production", "field"}


def _lock_buffer(secret: bytearray) -> None:
    if os.name != "posix" or not secret:
        return
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        buf = (ctypes.c_char * len(secret)).from_buffer(secret)
        libc.mlock(ctypes.addressof(buf), ctypes.c_size_t(len(secret)))
    except Exception:
        return


def _unlock_buffer(secret: bytearray) -> None:
    if os.name != "posix" or not secret:
        return
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        buf = (ctypes.c_char * len(secret)).from_buffer(secret)
        libc.munlock(ctypes.addressof(buf), ctypes.c_size_t(len(secret)))
    except Exception:
        return


def get_hmac_secret(env_key: str = "SENTRY_AUDIT_HMAC_KEY", secret: str | bytes | bytearray | None = None) -> bytearray:
    """Load the audit key into a mutable buffer so it can be scrubbed later."""
    if secret is None:
        secret = os.environ.get(env_key)
    if secret is None:
        if _production_mode():
            raise RuntimeError(f"{env_key} is required in production")
        secret = _DEV_SECRET
    if isinstance(secret, bytearray):
        raw = bytes(secret)
    elif isinstance(secret, bytes):
        raw = secret
    else:
        raw = secret.encode("utf-8")
    if _production_mode() and raw == _DEV_SECRET.encode("utf-8"):
        raise RuntimeError("default audit HMAC key is not allowed in production")
    buf = bytearray(raw)
    _lock_buffer(buf)
    return buf


@dataclass
class AuditLogger:
    """Append-only audit chain for SENTRY defensive events."""

    secret: str | bytes | bytearray | None = None
    env_key: str = "SENTRY_AUDIT_HMAC_KEY"
    _seq: int = 0
    _prev_hash: str = GENESIS_HASH
    _secret_buffer: bytearray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._secret_buffer = get_hmac_secret(self.env_key, self.secret)

    @property
    def secret_bytes(self) -> bytes:
        return bytes(self._secret_buffer)

    def rotate_secret(self, new_secret: str | bytes | bytearray) -> None:
        """Rotate the in-memory HMAC key for newly appended entries."""
        if _production_mode():
            raise RuntimeError("audit key rotation must happen before field deployment")
        self.wipe_secret()
        self._secret_buffer = get_hmac_secret(self.env_key, new_secret)
        self._seq = 0
        self._prev_hash = GENESIS_HASH

    def wipe_secret(self) -> None:
        """Overwrite the secret buffer before releasing it."""
        if not hasattr(self, "_secret_buffer"):
            return
        for i in range(len(self._secret_buffer)):
            self._secret_buffer[i] = 0
        _unlock_buffer(self._secret_buffer)

    def append(self, event: str, payload: dict[str, Any], timestamp_s: float | None = None) -> dict[str, Any]:
        ts = time.time() if timestamp_s is None else timestamp_s
        payload_hash = _sha256_hex(_canonical_json(payload))
        body = f"{self._seq}|{ts}|{event}|{payload_hash}|{self._prev_hash}"
        entry_hash = hmac.new(self.secret_bytes, body.encode("utf-8"), hashlib.sha256).hexdigest()

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
        entry["entry_integrity_hash"] = self._entry_integrity_hash(entry)
        self._seq += 1
        self._prev_hash = entry_hash
        return entry

    def _entry_integrity_hash(self, entry: dict[str, Any]) -> str:
        protected = {key: value for key, value in entry.items() if key != "entry_integrity_hash"}
        return hmac.new(self.secret_bytes, _canonical_json(protected), hashlib.sha256).hexdigest()

    def verify_chain(self, entries: list[dict[str, Any]]) -> bool:
        prev = GENESIS_HASH
        for i, entry in enumerate(entries):
            if entry.get("schema") != "audit_entry.v1" or entry.get("codename") != "SENTRY":
                return False
            if entry.get("seq") != i:
                return False
            if entry.get("prev_hash") != prev:
                return False
            try:
                body = (
                    f"{entry['seq']}|{entry['timestamp_s']}|{entry['event']}|"
                    f"{entry['payload_hash']}|{entry['prev_hash']}"
                )
            except KeyError:
                return False
            expected = hmac.new(self.secret_bytes, body.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(str(entry.get("entry_hash", "")), expected):
                return False
            integrity = entry.get("entry_integrity_hash")
            if integrity is not None and not hmac.compare_digest(str(integrity), self._entry_integrity_hash(entry)):
                return False
            prev = str(entry["entry_hash"])
        return True


def load_jsonl_entries(path: Path) -> list[dict[str, Any]]:
    """Read JSONL audit entries, failing closed on malformed rows."""
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError("audit row must be an object")
        entries.append(obj)
    return entries
