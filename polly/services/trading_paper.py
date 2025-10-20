from __future__ import annotations

import time
import uuid
from typing import Optional

from ..db import Database
from .trading import TradingGateway


class PaperTradingGateway(TradingGateway):
    def __init__(self, db: Database) -> None:
        self.db = db

    def _get_current_price(self, outcome_id: str) -> float:
        with self.db.as_conn() as conn:
            cur = conn.execute(
                "SELECT price FROM outcomes WHERE outcome_id=?",
                (outcome_id,),
            )
            row = cur.fetchone()
            if not row or row[0] is None:
                raise RuntimeError("Missing price for outcome")
            return float(row[0])

    def place_order(
        self,
        *,
        poll_id: str,
        outcome_id: str,
        side: str,
        size_usdc: float,
        research_id: Optional[str] = None,
        limit_price: Optional[float] = None,
    ) -> str:
        trade_id = str(uuid.uuid4())
        price = limit_price if limit_price is not None else self._get_current_price(outcome_id)
        if price <= 0:
            raise RuntimeError("Invalid price")
        quantity = size_usdc / price
        now = int(time.time())

        with self.db.as_conn() as conn:
            conn.execute(
                """
                INSERT INTO trades(id, poll_id, research_id, outcome_id, side, size_usdc, quantity, entry_price, entry_time, status, mode)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', 'paper')
                """,
                (trade_id, poll_id, research_id, outcome_id, side, size_usdc, quantity, price, now),
            )

        return trade_id

    def cancel_order(self, trade_id: str) -> None:  # pragma: no cover - noop for MVP
        return None

    def refresh_fills(self, trade_id: str) -> None:  # pragma: no cover - noop for MVP
        return None


