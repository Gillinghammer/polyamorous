from __future__ import annotations

import logging
import time

from ..config import Config
from ..db import Database

log = logging.getLogger(__name__)


class ResolutionService:
    def __init__(self, cfg: Config, db: Database) -> None:
        self.cfg = cfg
        self.db = db

    def resolve_all(self) -> int:
        """Close trades whose markets have resolved.

        MVP: If poll status != 'active' and trade is open, set exit_price = 1 if outcome name sort first is winning? For MVP, mark exit_price = entry_price (no PnL) to keep flow simple. Future: query official resolution.
        """
        now = int(time.time())
        closed = 0
        with self.db.as_conn() as conn:
            cur = conn.execute(
                """
                SELECT t.id, t.entry_price
                FROM trades t
                JOIN polls p ON p.poll_id = t.poll_id
                WHERE t.status='open' AND p.status != 'active'
                """
            )
            ids = [(row[0], float(row[1])) for row in cur.fetchall()]

            for trade_id, entry_price in ids:
                conn.execute(
                    "UPDATE trades SET status='closed', exit_price=?, exit_time=? WHERE id=?",
                    (entry_price, now, trade_id),
                )
                closed += 1

        log.info("resolved_trades", extra={"count": closed})
        return closed


