"""SQLite persistence for paper trades."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from ..models import PortfolioMetrics, Trade

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    question TEXT NOT NULL,
    selected_option TEXT NOT NULL,
    entry_odds REAL NOT NULL,
    stake_amount REAL NOT NULL,
    entry_timestamp TEXT NOT NULL,
    predicted_probability REAL NOT NULL,
    confidence REAL NOT NULL,
    research_id INTEGER,
    status TEXT NOT NULL,
    resolves_at TEXT NOT NULL,
    actual_outcome TEXT,
    profit_loss REAL,
    closed_at TEXT
);
"""


class TradeRepository:
    """Handles persistence of paper trades."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def record_trade(self, trade: Trade) -> Trade:
        """Insert a new trade and return the stored entity."""

        payload = asdict(trade)
        payload.pop("id", None)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO trades (
                    market_id, question, selected_option, entry_odds, stake_amount,
                    entry_timestamp, predicted_probability, confidence, research_id,
                    status, resolves_at, actual_outcome, profit_loss, closed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["market_id"],
                    payload["question"],
                    payload["selected_option"],
                    payload["entry_odds"],
                    payload["stake_amount"],
                    payload["entry_timestamp"].isoformat(),
                    payload["predicted_probability"],
                    payload["confidence"],
                    payload["research_id"],
                    payload["status"],
                    payload["resolves_at"].isoformat(),
                    payload["actual_outcome"],
                    payload["profit_loss"],
                    payload["closed_at"].isoformat() if payload["closed_at"] else None,
                ),
            )
            trade_id = cursor.lastrowid
        return Trade(id=trade_id, **payload)

    def update_trade_outcome(self, trade_id: int, actual_outcome: str, profit_loss: float) -> None:
        """Update a trade with resolution data."""

        closed_at = datetime.now(tz=timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE trades
                SET actual_outcome = ?, profit_loss = ?, status = ?, closed_at = ?
                WHERE id = ?
                """,
                (actual_outcome, profit_loss, "won" if profit_loss > 0 else "lost", closed_at, trade_id),
            )

    def list_recent(self, limit: int = 5) -> List[Trade]:
        """Return recent trades for the dashboard."""

        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT * FROM trades
                ORDER BY entry_timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
        return [self._row_to_trade(row) for row in rows]

    def metrics(self) -> PortfolioMetrics:
        """Compute aggregate portfolio metrics."""

        with self._connect() as connection:
            active_count = connection.execute(
                "SELECT COUNT(*) FROM trades WHERE status = 'active'"
            ).fetchone()[0]

            resolved_rows = connection.execute(
                """
                SELECT COUNT(*) AS total, SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) AS wins,
                       SUM(stake_amount) AS total_stake, SUM(COALESCE(profit_loss, 0)) AS total_profit,
                       MIN(entry_timestamp) AS first_entry
                FROM trades
                WHERE status IN ('won', 'lost')
                """
            ).fetchone()

        total_resolved = resolved_rows[0] or 0
        wins = resolved_rows[1] or 0
        total_stake = resolved_rows[2] or 0.0
        total_profit = resolved_rows[3] or 0.0
        first_entry_raw = resolved_rows[4]

        win_rate = (wins / total_resolved) if total_resolved else 0.0
        average_profit = (total_profit / total_resolved) if total_resolved else 0.0

        projected_apr = 0.0
        if total_stake and first_entry_raw:
            first_entry = datetime.fromisoformat(first_entry_raw)
            days = max((datetime.now(tz=timezone.utc) - first_entry).days, 1)
            base = (total_profit / total_stake) + 1
            if base > 0:
                projected_apr = base ** (365 / days) - 1

        recent_trades = self.list_recent()

        return PortfolioMetrics(
            active_positions=int(active_count),
            win_rate=win_rate,
            total_profit=total_profit,
            average_profit=average_profit,
            projected_apr=projected_apr,
            recent_trades=recent_trades,
        )

    def _row_to_trade(self, row: sqlite3.Row) -> Trade:
        """Convert sqlite row to Trade dataclass."""

        return Trade(
            id=row["id"],
            market_id=row["market_id"],
            question=row["question"],
            selected_option=row["selected_option"],
            entry_odds=row["entry_odds"],
            stake_amount=row["stake_amount"],
            entry_timestamp=datetime.fromisoformat(row["entry_timestamp"]),
            predicted_probability=row["predicted_probability"],
            confidence=row["confidence"],
            research_id=row["research_id"],
            status=row["status"],
            resolves_at=datetime.fromisoformat(row["resolves_at"]),
            actual_outcome=row["actual_outcome"],
            profit_loss=row["profit_loss"],
            closed_at=datetime.fromisoformat(row["closed_at"]) if row["closed_at"] else None,
        )

    def _connect(self) -> sqlite3.Connection:
        """Create a SQLite connection with row factory."""

        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection
