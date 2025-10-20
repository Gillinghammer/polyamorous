from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS migrations (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  applied_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);

/* Core tables */
CREATE TABLE IF NOT EXISTS polls (
  poll_id TEXT PRIMARY KEY,
  question TEXT NOT NULL,
  url TEXT NOT NULL,
  category TEXT,
  end_time INTEGER NOT NULL,
  status TEXT,
  archived INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_polls_end_time ON polls(end_time);
CREATE INDEX IF NOT EXISTS idx_polls_status ON polls(status);

CREATE TABLE IF NOT EXISTS outcomes (
  outcome_id TEXT PRIMARY KEY,
  poll_id TEXT NOT NULL REFERENCES polls(poll_id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  price REAL,
  last_price_at INTEGER,
  price_source TEXT
);

CREATE TABLE IF NOT EXISTS research (
  id TEXT PRIMARY KEY,
  poll_id TEXT NOT NULL REFERENCES polls(poll_id) ON DELETE CASCADE,
  started_at INTEGER,
  completed_at INTEGER,
  recommendation TEXT CHECK(recommendation IN ('enter','pass')),
  confidence REAL,
  position_size_pct REAL,
  rationale TEXT,
  provider TEXT,
  meta_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_research_poll_id ON research(poll_id);

CREATE TABLE IF NOT EXISTS trades (
  id TEXT PRIMARY KEY,
  poll_id TEXT NOT NULL REFERENCES polls(poll_id) ON DELETE CASCADE,
  research_id TEXT REFERENCES research(id) ON DELETE SET NULL,
  outcome_id TEXT NOT NULL REFERENCES outcomes(outcome_id) ON DELETE CASCADE,
  side TEXT CHECK(side IN ('buy','sell')),
  size_usdc REAL,
  quantity REAL,
  entry_price REAL,
  entry_time INTEGER,
  exit_price REAL,
  exit_time INTEGER,
  status TEXT CHECK(status IN ('open','closed')),
  mode TEXT CHECK(mode IN ('paper','real')) DEFAULT 'paper',
  provider TEXT,
  provider_order_id TEXT,
  fee REAL
);

CREATE INDEX IF NOT EXISTS idx_trades_poll_status_mode ON trades(poll_id, status, mode);

CREATE TABLE IF NOT EXISTS citations (
  id TEXT PRIMARY KEY,
  research_id TEXT NOT NULL REFERENCES research(id) ON DELETE CASCADE,
  kind TEXT CHECK(kind IN ('web','x')),
  title TEXT,
  url TEXT NOT NULL,
  snippet TEXT,
  source TEXT,
  published_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_citations_research_kind ON citations(research_id, kind);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


@dataclass
class Database:
    path: Path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def as_conn(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.as_conn() as conn:
            conn.executescript(SCHEMA_SQL)

    def set_setting(self, key: str, value: str) -> None:
        with self.as_conn() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self.as_conn() as conn:
            cur = conn.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cur.fetchone()
            return row[0] if row else default


