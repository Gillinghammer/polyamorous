from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from ..db import Database
from ..models import AgentDecisions

log = logging.getLogger(__name__)


@dataclass
class PortfolioMetrics:
    available_cash: float
    unrealized_pnl: float
    realized_pnl: float


class PortfolioService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_starting_balance(self) -> float:
        val = self.db.get_setting("starting_balance_usdc", "0") or "0"
        try:
            return float(val)
        except Exception:
            return 0.0

    def compute_metrics(self) -> PortfolioMetrics:
        starting = self.get_starting_balance()
        with self.db.as_conn() as conn:
            cur = conn.execute(
                "SELECT COALESCE(SUM(size_usdc), 0) FROM trades WHERE status='open'"
            )
            open_cost = float(cur.fetchone()[0] or 0)

            cur = conn.execute(
                "SELECT COALESCE(SUM((exit_price - entry_price) * quantity), 0) FROM trades WHERE status='closed'"
            )
            realized = float(cur.fetchone()[0] or 0)

        # Unrealized requires current price; approximate 0 for MVP (updated later)
        unrealized = 0.0
        available = max(0.0, starting - open_cost + realized)
        return PortfolioMetrics(available_cash=available, unrealized_pnl=unrealized, realized_pnl=realized)

    def get_agent_window_days(self) -> int:
        val = self.db.get_setting("agent_window_days", "3") or "3"
        try:
            return int(val)
        except Exception:
            return 3

    def run_agent_once(self, trading_gateway, window_days: int) -> AgentDecisions:
        """Select eligible polls and attempt entries respecting available cash.

        Simplified MVP: choose polls without open trades and with research recommending enter.
        """
        metrics = self.compute_metrics()
        processed = entered = skipped = 0
        now = int(time.time())
        window_end = now + window_days * 86400

        with self.db.as_conn() as conn:
            cur = conn.execute(
                """
                SELECT p.poll_id, p.question, r.id AS research_id, r.position_size_pct
                FROM polls p
                JOIN research r ON r.poll_id = p.poll_id AND r.recommendation='enter'
                WHERE p.archived=0 AND p.end_time BETWEEN ? AND ?
                  AND NOT EXISTS (
                    SELECT 1 FROM trades t WHERE t.poll_id = p.poll_id AND t.status='open'
                  )
                ORDER BY p.end_time ASC
                LIMIT 50
                """,
                (now, window_end),
            )
            rows = cur.fetchall()

        for row in rows:
            processed += 1
            pct = float(row["position_size_pct"] or 0)
            size = max(0.0, pct) * metrics.available_cash
            if size <= 0.0 or size > metrics.available_cash:
                skipped += 1
                continue
            try:
                trading_gateway.place_order(
                    poll_id=row["poll_id"],
                    outcome_id=self._select_primary_outcome(row["poll_id"]),
                    side="buy",
                    size_usdc=size,
                    research_id=row["research_id"],
                )
                entered += 1
                metrics = self.compute_metrics()  # refresh after entry
            except Exception as exc:
                log.error("agent_place_failed", extra={"poll_id": row["poll_id"], "error": str(exc)})
                skipped += 1

        return AgentDecisions(processed=processed, entered=entered, skipped=skipped)

    def _select_primary_outcome(self, poll_id: str) -> str:
        with self.db.as_conn() as conn:
            cur = conn.execute(
                "SELECT outcome_id FROM outcomes WHERE poll_id=? ORDER BY name ASC LIMIT 1",
                (poll_id,),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Missing outcomes for poll")
            return str(row[0])


