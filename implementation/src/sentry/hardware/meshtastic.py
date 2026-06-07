"""Meshtastic LoRa mesh alert relay."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sentry.hardware import adapter_status

LOG = logging.getLogger("SENTRY")


@dataclass
class MeshtasticConfig:
    device_path: str = "/dev/ttyACM0"
    fallback_spool: Path | None = None
    max_payload_bytes: int = 200


def probe(config: MeshtasticConfig | None = None) -> dict[str, Any]:
    cfg = config or MeshtasticConfig()
    try:
        from meshtastic.serial_interface import SerialInterface  # noqa: F401
    except ImportError:
        spool = cfg.fallback_spool or Path("/var/lib/sentry/meshtastic_spool.jsonl")
        return adapter_status("meshtastic", False, f"meshtastic not installed; spool={spool}")
    if not Path(cfg.device_path).exists():
        return adapter_status("meshtastic", False, f"device missing: {cfg.device_path}")
    return adapter_status("meshtastic", True, f"device={cfg.device_path}")


class MeshtasticRelay:
    """Publish compact SENTRY alert summaries over Meshtastic or spool file."""

    def __init__(self, config: MeshtasticConfig | None = None) -> None:
        self.config = config or MeshtasticConfig()
        self._iface = None
        self._available = False
        try:
            from meshtastic.serial_interface import SerialInterface

            if Path(self.config.device_path).exists():
                self._iface = SerialInterface(devPath=self.config.device_path)
                self._available = True
        except Exception as exc:  # noqa: BLE001
            LOG.info("SENTRY Meshtastic unavailable: %s", exc)

    @property
    def available(self) -> bool:
        return self._available

    def close(self) -> None:
        if self._iface is not None:
            try:
                self._iface.close()
            except Exception:  # noqa: BLE001
                pass
            self._iface = None

    def publish(self, alert: dict[str, Any]) -> bool:
        payload = {
            "schema": "omen_alert.v1",
            "codename": "SENTRY",
            "node_id": alert.get("node_id"),
            "level": alert.get("level"),
            "threat_score": alert.get("threat_score"),
            "seq": alert.get("seq"),
            "timestamp_s": alert.get("timestamp_s"),
        }
        text = json.dumps(payload, separators=(",", ":"))
        if len(text.encode("utf-8")) > self.config.max_payload_bytes:
            text = text[: self.config.max_payload_bytes]

        if self._available and self._iface is not None:
            try:
                self._iface.sendText(text)
                return True
            except Exception as exc:  # noqa: BLE001
                LOG.warning("SENTRY Meshtastic send failed: %s", exc)

        spool = self.config.fallback_spool or Path("/var/lib/sentry/meshtastic_spool.jsonl")
        try:
            spool.parent.mkdir(parents=True, exist_ok=True)
            with spool.open("a", encoding="utf-8") as fh:
                fh.write(text + "\n")
            return True
        except OSError as exc:
            LOG.warning("SENTRY Meshtastic spool failed: %s", exc)
            return False
