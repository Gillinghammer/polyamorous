"""SQLite persistence for paper trades."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from polly.models import PortfolioMetrics, Trade

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    question TEXT NOT NULL,
    category TEXT,
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
    closed_at TEXT,
    trade_mode TEXT DEFAULT 'paper',
    order_id TEXT,
    event_id TEXT,
    event_title TEXT,
    is_grouped BOOLEAN DEFAULT 0,
    group_strategy TEXT
);

CREATE TABLE IF NOT EXISTS market_groups (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    end_date TEXT NOT NULL,
    liquidity REAL,
    volume_24h REAL,
    enable_neg_risk BOOLEAN,
    show_all_outcomes BOOLEAN,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    strategy_type TEXT,
    total_stake REAL,
    combined_ev REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES market_groups(id)
);
"""


class TradeRepository:
    """Handles persistence of paper trades."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            self._ensure_columns(connection)

    def record_trade(self, trade: Trade) -> Trade:
        """Insert a new trade and return the stored entity."""

        payload = asdict(trade)
        payload.pop("id", None)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO trades (
                    market_id, question, category, selected_option, entry_odds, stake_amount,
                    entry_timestamp, predicted_probability, confidence, research_id,
                    status, resolves_at, actual_outcome, profit_loss, closed_at,
                    trade_mode, order_id, event_id, event_title, is_grouped, group_strategy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["market_id"],
                    payload["question"],
                    payload.get("category"),
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
                    payload.get("trade_mode", "paper"),
                    payload.get("order_id"),
                    payload.get("event_id"),
                    payload.get("event_title"),
                    payload.get("is_grouped", False),
                    payload.get("group_strategy"),
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

    def metrics(self, starting_cash: float = 0.0, filter_mode: str | None = None, real_balance: float | None = None) -> PortfolioMetrics:
        """Compute aggregate portfolio metrics including balances and category stats.
        
        Args:
            starting_cash: Starting cash balance for paper trading
            filter_mode: Optional filter for trade mode ("paper" or "real"). If None, shows all trades.
            real_balance: Actual on-chain balance for real mode (overrides paper tracking formula)
        """

        mode_filter = f"AND trade_mode = '{filter_mode}'" if filter_mode else ""
        
        with self._connect() as connection:
            active_count = connection.execute(
                f"SELECT COUNT(*) FROM trades WHERE status = 'active' {mode_filter}"
            ).fetchone()[0]

            resolved_rows = connection.execute(
                f"""
                SELECT COUNT(*) AS total, SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) AS wins,
                       SUM(stake_amount) AS total_stake, SUM(COALESCE(profit_loss, 0)) AS total_profit,
                       MIN(entry_timestamp) AS first_entry
                FROM trades
                WHERE status IN ('won', 'lost') {mode_filter}
                """
            ).fetchone()

            # Largest win/loss and per-category realized profit
            cat_rows = connection.execute(
                f"""
                SELECT COALESCE(category, 'Unknown') AS category, SUM(COALESCE(profit_loss,0)) AS profit
                FROM trades
                WHERE status IN ('won','lost','closed') {mode_filter}
                GROUP BY category
                """
            ).fetchall()
            realized_rows = connection.execute(
                f"""
                SELECT MAX(COALESCE(profit_loss,0)) AS max_win,
                       MIN(COALESCE(profit_loss,0)) AS max_loss
                FROM trades
                WHERE status IN ('won','lost','closed') {mode_filter}
                """
            ).fetchone()

            # Balances
            cash_in_play = connection.execute(
                f"SELECT SUM(stake_amount) FROM trades WHERE status = 'active' {mode_filter}"
            ).fetchone()[0] or 0.0
            realized_total = connection.execute(
                f"SELECT SUM(COALESCE(profit_loss,0)) FROM trades WHERE status IN ('won','lost','closed') {mode_filter}"
            ).fetchone()[0] or 0.0

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

        profit_by_category = {row[0]: float(row[1] or 0.0) for row in cat_rows}
        best_category = None
        worst_category = None
        if profit_by_category:
            best_category = max(profit_by_category, key=lambda k: profit_by_category[k])
            worst_category = min(profit_by_category, key=lambda k: profit_by_category[k])

        largest_win = float(realized_rows[0] or 0.0)
        largest_loss = float(realized_rows[1] or 0.0)

        # Use real on-chain balance if provided (real mode), otherwise use paper tracking formula
        if real_balance is not None:
            cash_available = float(real_balance)
        else:
            cash_available = float(starting_cash) + float(realized_total) - float(cash_in_play)

        return PortfolioMetrics(
            active_positions=int(active_count),
            win_rate=win_rate,
            total_profit=total_profit,
            average_profit=average_profit,
            projected_apr=projected_apr,
            recent_trades=recent_trades,
            largest_win=largest_win,
            largest_loss=largest_loss,
            best_category=best_category,
            worst_category=worst_category,
            profit_by_category=profit_by_category,
            cash_available=cash_available,
            cash_in_play=float(cash_in_play),
        )

    def list_active(self, filter_mode: str | None = None) -> List[Trade]:
        """List all active trades, optionally filtered by mode."""
        mode_filter = f"AND trade_mode = '{filter_mode}'" if filter_mode else ""
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                SELECT * FROM trades
                WHERE status = 'active' {mode_filter}
                ORDER BY entry_timestamp DESC
                """
            )
            rows = cursor.fetchall()
        return [self._row_to_trade(row) for row in rows]

    def list_history(self, limit: int = 20, filter_mode: str | None = None) -> List[Trade]:
        """List recently closed trades (won/lost), optionally filtered by mode."""
        mode_filter = f"AND trade_mode = '{filter_mode}'" if filter_mode else ""
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                SELECT * FROM trades
                WHERE status IN ('won','lost','closed') {mode_filter}
                ORDER BY closed_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
        return [self._row_to_trade(row) for row in rows]

    def close_trade(self, trade_id: int, exit_price: float, timestamp: datetime | None = None) -> None:
        """Manually close an active trade at a given price; computes PnL and marks closed."""
        if timestamp is None:
            timestamp = datetime.now(tz=timezone.utc)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM trades WHERE id = ?",
                (trade_id,),
            ).fetchone()
            if not row:
                return
            t = self._row_to_trade(row)
            shares = _compute_shares(t.stake_amount, t.entry_odds)
            exit_value = shares * exit_price
            entry_cost = t.stake_amount
            pnl = float(exit_value - entry_cost)
            connection.execute(
                """
                UPDATE trades
                SET status = ?, profit_loss = ?, closed_at = ?
                WHERE id = ?
                """,
                ("closed", pnl, timestamp.isoformat(), trade_id),
            )


    def find_latest_by_market(self, market_id: str) -> Trade | None:
        """Return the most recent trade for a given market, if any."""

        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT * FROM trades
                WHERE market_id = ?
                ORDER BY entry_timestamp DESC
                LIMIT 1
                """,
                (market_id,),
            )
            row = cursor.fetchone()
        return self._row_to_trade(row) if row else None
    
    def save_trade_group(self, trades: List[Trade], strategy_type: str = "multi_position") -> List[Trade]:
        """Save multiple related trades as a group strategy."""
        if not trades:
            return []
        
        saved_trades = []
        event_id = trades[0].event_id
        total_stake = sum(t.stake_amount for t in trades)
        
        # Save each trade
        for trade in trades:
            saved_trade = self.record_trade(trade)
            saved_trades.append(saved_trade)
        
        # Record the group strategy
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO trade_groups (event_id, strategy_type, total_stake, combined_ev, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    strategy_type,
                    total_stake,
                    0.0,  # Calculate combined EV externally
                    datetime.now(tz=timezone.utc).isoformat(),
                ),
            )
        
        return saved_trades
    
    def get_grouped_trades(self, event_id: str | None = None) -> dict[str, List[Trade]]:
        """Retrieve trades grouped by event_id."""
        with self._connect() as connection:
            if event_id:
                cursor = connection.execute(
                    """
                    SELECT * FROM trades
                    WHERE event_id = ? AND is_grouped = 1
                    ORDER BY entry_timestamp DESC
                    """,
                    (event_id,),
                )
            else:
                cursor = connection.execute(
                    """
                    SELECT * FROM trades
                    WHERE is_grouped = 1 AND event_id IS NOT NULL
                    ORDER BY entry_timestamp DESC
                    """
                )
            rows = cursor.fetchall()
        
        # Group by event_id
        grouped = {}
        for row in rows:
            trade = self._row_to_trade(row)
            if trade.event_id:
                if trade.event_id not in grouped:
                    grouped[trade.event_id] = []
                grouped[trade.event_id].append(trade)
        
        return grouped

    def _row_to_trade(self, row: sqlite3.Row) -> Trade:
        """Convert sqlite row to Trade dataclass."""

        # Handle new columns with backward compatibility
        row_keys = row.keys()
        
        try:
            trade_mode = row["trade_mode"] if "trade_mode" in row_keys else "paper"
        except (KeyError, IndexError):
            trade_mode = "paper"
        
        try:
            order_id = row["order_id"] if "order_id" in row_keys else None
        except (KeyError, IndexError):
            order_id = None
            
        try:
            event_id = row["event_id"] if "event_id" in row_keys else None
        except (KeyError, IndexError):
            event_id = None
            
        try:
            event_title = row["event_title"] if "event_title" in row_keys else None
        except (KeyError, IndexError):
            event_title = None
            
        try:
            is_grouped = bool(row["is_grouped"]) if "is_grouped" in row_keys else False
        except (KeyError, IndexError):
            is_grouped = False
            
        try:
            group_strategy = row["group_strategy"] if "group_strategy" in row_keys else None
        except (KeyError, IndexError):
            group_strategy = None

        return Trade(
            id=row["id"],
            market_id=row["market_id"],
            question=row["question"],
            category=row["category"],
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
            trade_mode=trade_mode,
            order_id=order_id,
            event_id=event_id,
            event_title=event_title,
            is_grouped=is_grouped,
            group_strategy=group_strategy,
        )

    def _connect(self) -> sqlite3.Connection:
        """Create a SQLite connection with row factory."""

        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_columns(self, connection: sqlite3.Connection) -> None:
        """Ensure new additive columns exist for backward compatibility."""
        try:
            info = connection.execute("PRAGMA table_info(trades)").fetchall()
            names = {row[1] for row in info}
            if "category" not in names:
                connection.execute("ALTER TABLE trades ADD COLUMN category TEXT")
            if "trade_mode" not in names:
                connection.execute("ALTER TABLE trades ADD COLUMN trade_mode TEXT DEFAULT 'paper'")
            if "order_id" not in names:
                connection.execute("ALTER TABLE trades ADD COLUMN order_id TEXT")
            if "event_id" not in names:
                connection.execute("ALTER TABLE trades ADD COLUMN event_id TEXT")
            if "event_title" not in names:
                connection.execute("ALTER TABLE trades ADD COLUMN event_title TEXT")
            if "is_grouped" not in names:
                connection.execute("ALTER TABLE trades ADD COLUMN is_grouped BOOLEAN DEFAULT 0")
            if "group_strategy" not in names:
                connection.execute("ALTER TABLE trades ADD COLUMN group_strategy TEXT")
        except Exception:
            # best-effort; avoid failing app startup
            pass


def _compute_shares(stake_amount: float, entry_odds: float) -> float:
    """Compute number of shares purchased for a binary contract.

    Assumes stake buys shares at `entry_odds` price per share.
    """
    if entry_odds <= 0:
        return 0.0
    return float(stake_amount / entry_odds)
