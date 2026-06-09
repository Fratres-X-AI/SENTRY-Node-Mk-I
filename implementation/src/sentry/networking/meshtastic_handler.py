"""Meshtastic LoRa mesh handler — low-bandwidth OMEN alert relay."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from sentry.hardware import adapter_status

LOG = logging.getLogger("SENTRY")


@dataclass
class MeshNodeConfig:
    node_id: str = "sentry-pi-zero-001"
    device_path: str = "/dev/ttyACM0"
    mesh_alias: str = "SENTRY"
    max_payload_bytes: int = 200


@dataclass
class MeshtasticHandlerConfig:
    local: MeshNodeConfig = field(default_factory=MeshNodeConfig)
    peers: list[str] = field(default_factory=lambda: ["sentry-pi-zero-002", "sentry-pi-zero-003"])
    spool_path: Path = Path("/var/lib/sentry/meshtastic_spool.jsonl")
    receive_spool: Path = Path("/var/lib/sentry/meshtastic_inbox.jsonl")


class MeshtasticHandler:
    """Send/receive compact SENTRY alerts over Meshtastic mesh."""

    def __init__(self, config: MeshtasticHandlerConfig | None = None) -> None:
        self.config = config or MeshtasticHandlerConfig()
        self._iface = None
        self._available = False
        self._subs: list[Callable[[dict[str, Any]], None]] = []
        self._connect()

    def _connect(self) -> None:
        try:
            from meshtastic.serial_interface import SerialInterface

            path = self.config.local.device_path
            if Path(path).exists():
                self._iface = SerialInterface(devPath=path)
                self._available = True
                LOG.info("SENTRY Meshtastic connected: %s", path)
        except Exception as exc:  # noqa: BLE001
            LOG.info("SENTRY Meshtastic unavailable: %s", exc)

    @property
    def available(self) -> bool:
        return self._available

    def probe(self) -> dict[str, Any]:
        if self._available:
            return adapter_status("meshtastic_handler", True, self.config.local.device_path)
        return adapter_status(
            "meshtastic_handler",
            False,
            f"spool={self.config.spool_path}",
        )

    def close(self) -> None:
        if self._iface is not None:
            try:
                self._iface.close()
            except Exception:  # noqa: BLE001
                pass
            self._iface = None

    def _omen_payload(self, alert: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": "omen_alert.v1",
            "codename": "SENTRY",
            "node_id": alert.get("node_id"),
            "level": alert.get("level"),
            "threat_score": alert.get("threat_score"),
            "seq": alert.get("seq"),
            "timestamp_s": alert.get("timestamp_s"),
            "mesh_from": self.config.local.node_id,
        }

    def send_alert(self, alert: dict[str, Any]) -> bool:
        payload = self._omen_payload(alert)
        text = json.dumps(payload, separators=(",", ":"))
        if len(text.encode("utf-8")) > self.config.local.max_payload_bytes:
            text = text[: self.config.local.max_payload_bytes]

        if self._available and self._iface is not None:
            try:
                self._iface.sendText(text)
                LOG.info("SENTRY mesh TX level=%s", payload.get("level"))
                return True
            except Exception as exc:  # noqa: BLE001
                LOG.warning("SENTRY mesh TX failed: %s", exc)

        return self._spool_write(self.config.spool_path, text)

    def _spool_write(self, path: Path, line: str) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            return True
        except OSError as exc:
            LOG.warning("SENTRY mesh spool failed: %s", exc)
            return False

    def poll_inbox(self) -> list[dict[str, Any]]:
        inbox = self.config.receive_spool
        if not inbox.exists():
            return []
        messages: list[dict[str, Any]] = []
        for line in inbox.read_text(encoding="utf-8").strip().splitlines()[-20:]:
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return messages

    def relay_peer_summary(self) -> dict[str, Any]:
        return {
            "local_node": self.config.local.node_id,
            "peers": self.config.peers,
            "mesh_available": self._available,
            "inbox_count": len(self.poll_inbox()),
        }

    def chain_auto_join(self, peer_ids: list[str]) -> dict[str, Any]:
        """
        Register chain topology peers for post-landing mesh join.
        Spool-based when hardware absent — defensive relay only.
        """
        self.config.peers = list(dict.fromkeys(peer_ids))
        result = {
            "codename": "SENTRY",
            "local_node": self.config.local.node_id,
            "peers_registered": self.config.peers,
            "mesh_available": self._available,
            "joined": self._available,
        }
        if not self._available:
            self._spool_write(
                self.config.spool_path,
                json.dumps({"event": "chain_auto_join", **result}, separators=(",", ":")),
            )
        return result
