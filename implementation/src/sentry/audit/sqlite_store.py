"""Lightweight SQLite event store for SENTRY edge nodes."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AuditStoreConfig:
    path: Path = Path("validation/reports/audit_log.db")
    max_rows: int = 10_000
    wal: bool = True


class AuditStore:
    """Bounded SQLite log: all events first, critical events still flush to HMAC JSONL."""

    def __init__(self, config: AuditStoreConfig | None = None) -> None:
        self.config = config or AuditStoreConfig()
        self.config.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.config.path)
        conn.row_factory = sqlite3.Row
        if self.config.wal:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_s REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    level TEXT,
                    node_id TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp_s);
                CREATE INDEX IF NOT EXISTS idx_events_level ON events(level);
                """
            )
            conn.commit()

    def append(self, event_type: str, payload: dict[str, Any], timestamp_s: float | None = None) -> int:
        ts = time.time() if timestamp_s is None else timestamp_s
        level = payload.get("level")
        node_id = payload.get("node_id")
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO events (timestamp_s, event_type, level, node_id, payload_json) VALUES (?, ?, ?, ?, ?)",
                (ts, event_type, level, node_id, payload_json),
            )
            conn.execute(
                """
                DELETE FROM events
                WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT ?)
                """,
                (self.config.max_rows,),
            )
            conn.commit()
            row_id = cur.lastrowid
            if row_id is None:
                raise RuntimeError("SQLite insert did not return a row id")
            return row_id

    def recent(self, limit: int = 50, level: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM events"
        params: tuple[Any, ...] = ()
        if level is not None:
            sql += " WHERE level = ?"
            params = (level,)
        sql += " ORDER BY id DESC LIMIT ?"
        params = (*params, limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            out.append(item)
        return out

    def count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
