from __future__ import annotations

import json
import os
from pathlib import Path

from sentry.audit import AuditLogger, AuditStore, AuditStoreConfig
from sentry.chaos import ChaosStreamParser
from sentry.networking.meshtastic_handler import MeshtasticHandler, MeshtasticHandlerConfig, MeshNodeConfig
from sentry.networking.p2p_mesh import build_intel_summary, verify_summary
from sentry.scoring import ThreatScorer, ThreatThresholds
from sentry.sensors.ghost_monitor import GhostMonitor, GhostMonitorConfig
from sentry.sensors.whisper_detector import WhisperDetector, WhisperDetectorConfig, shannon_entropy
from sentry.tamper_response import TamperWipeConfig, handle_tamper


def test_audit_detects_single_character_tamper() -> None:
    audit = AuditLogger(secret="test-secret")
    entries = [audit.append("boot", {"node": "a"}), audit.append("alert", {"level": "RED"})]
    assert audit.verify_chain(entries)
    tampered = [dict(row) for row in entries]
    first = "1" if tampered[1]["entry_hash"][0] == "0" else "0"
    tampered[1]["entry_hash"] = first + tampered[1]["entry_hash"][1:]
    assert not audit.verify_chain(tampered)


def test_audit_store_prunes_rows(tmp_path: Path) -> None:
    store = AuditStore(AuditStoreConfig(path=tmp_path / "audit.db", max_rows=2))
    store.append("alert", {"node_id": "n", "level": "CLEAR"})
    store.append("alert", {"node_id": "n", "level": "YELLOW"})
    store.append("alert", {"node_id": "n", "level": "RED"})
    assert store.count() == 2
    assert store.recent(1)[0]["payload"]["level"] == "RED"


def test_whisper_entropy_flags_encoded_text() -> None:
    detector = WhisperDetector(WhisperDetectorConfig(entropy_threshold=4.0))
    encoded = "QWxhZGRpbjpvcGVuIHNlc2FtZQ==" * 4
    result = detector.analyse_text(encoded)
    assert shannon_entropy(encoded) > 0
    assert result.suspicious


def test_ghost_monitor_regular_deltas_flag(monkeypatch) -> None:
    values = iter([0, 1024, 2048, 3072])

    class Counters:
        def __init__(self, value: int) -> None:
            self.bytes_sent = value
            self.bytes_recv = 0

    monkeypatch.setattr("sentry.sensors.ghost_monitor.psutil.net_io_counters", lambda pernic=False: Counters(next(values)))
    monitor = GhostMonitor(GhostMonitorConfig(sample_interval_s=0.0, min_delta_bytes=100.0))
    assert not monitor.sample(now_s=1.0, force=True).suspicious
    monitor.sample(now_s=2.0, force=True)
    monitor.sample(now_s=3.0, force=True)
    assert monitor.sample(now_s=4.0, force=True).suspicious


def test_scoring_darkspace_bumps() -> None:
    scorer = ThreatScorer()
    yellow = scorer.score({"fused_score": 0.1, "flags": {"steganography_suspected": True}}, ThreatThresholds())
    assert yellow["level"] == "YELLOW"
    orange = scorer.score({"fused_score": 0.4, "flags": {"passive_network_anomaly": True}}, ThreatThresholds())
    assert orange["level"] == "ORANGE"


def test_p2p_summary_signature(monkeypatch) -> None:
    monkeypatch.setenv("SENTRY_MESH_SIGN_KEY", "x" * 32)
    summary = build_intel_summary(
        {
            "node_id": "n",
            "level": "ORANGE",
            "threat_score": 0.7,
            "seq": 2,
            "timestamp_s": 1.0,
            "sensor_event": {"flags": {"passive_network_anomaly": True, "whisper_entropy": 5.0}},
        }
    )
    assert verify_summary(summary)
    summary["level"] = "RED"
    assert not verify_summary(summary)


def test_meshtastic_hold_suppresses_tx(tmp_path: Path) -> None:
    handler = MeshtasticHandler(
        MeshtasticHandlerConfig(
            local=MeshNodeConfig(node_id="n"),
            spool_path=tmp_path / "out.jsonl",
            receive_spool=tmp_path / "in.jsonl",
        )
    )
    handler.set_hold_mode(True)
    assert not handler.send_alert({"level": "HOLD", "seq": 1})
    assert not (tmp_path / "out.jsonl").exists()
    assert "mesh_tx_suppressed" in (tmp_path / "in.jsonl").read_text(encoding="utf-8")


def test_chaos_parser_discards_bad_data(tmp_path: Path) -> None:
    path = tmp_path / "chaos.jsonl"
    good = {
        "node_id": "n",
        "sequence_id": 1,
        "metrics": {"rf_2g4_dbm": 10.0, "rf_5g8_dbm": 10.0, "acoustic_fft_peak_hz": 220.0},
    }
    path.write_text('{"broken":\n' + json.dumps(good) + "\n" + json.dumps({"sequence_id": [1]}) + "\n")
    report = ChaosStreamParser(max_window=1).parse_file(path)
    assert report.accepted == 1
    assert report.malformed == 1
    assert report.rejected == 1
    assert report.window_size == 1


def test_tamper_response_zero_fills_and_deletes(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "secret.bin"
    target.write_bytes(b"secret" * 1000)
    monkeypatch.setenv("SENTRY_AUDIT_HMAC_KEY", "k" * 32)
    audit = AuditLogger(secret="k" * 32)
    result = handle_tamper(
        audit,
        TamperWipeConfig(wipe_paths=[str(target)], wipe_env_keys=["SENTRY_AUDIT_HMAC_KEY"], dry_run=False),
    )
    assert str(target) in result["wiped"]
    assert not target.exists()
    assert "SENTRY_AUDIT_HMAC_KEY" not in os.environ
