from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..config import Config
from ..db import Database
from .polymarket_api import PolymarketAPI

log = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, cfg: Config, db: Database) -> None:
        self.cfg = cfg
        self.db = db
        self.api = PolymarketAPI(cfg)

    def ingest_markets(self, open_only: bool = True, since_hours: Optional[int] = None, top_n: Optional[int] = None) -> int:
        markets = self.api.get_markets()

        cutoff: Optional[datetime] = None
        if since_hours:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)

        # First pass: open/time filters (require tokens and a valid future end time)
        initial: list = []
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for m in markets:
            status_value = str(m.get("status") or "").lower()
            is_closed_flag = bool(m.get("closed", False)) or status_value in {"closed", "resolved", "ended"}
            if open_only and is_closed_flag:
                continue
            # Require a valid future end timestamp, and optionally honor cutoff
            end_iso_tmp = (
                m.get("end_date_iso")
                or m.get("end_date")
                or m.get("event_end_date")
                or m.get("game_start_time")
                or m.get("close_time")
                or m.get("resolution_time")
            )
            if not end_iso_tmp:
                continue
            try:
                end_tmp_ts = int(datetime.fromisoformat(str(end_iso_tmp).replace("Z", "+00:00")).timestamp())
            except Exception:
                continue
            if cutoff is not None and end_tmp_ts < int(cutoff.timestamp()):
                continue
            m["_end_ts"] = end_tmp_ts
            # Require at least one token (outcome) for display
            if not (m.get("tokens") or []):
                continue
            initial.append(m)
        markets = initial

        # Optional Top-N: exclude sports and rank by a simple score
        if top_n:
            sports_keywords = [
                "sports",
                "esports",
                "nfl",
                "nba",
                "mlb",
                "nhl",
                "soccer",
                "football",
            ]
            ranked: list = []
            for m in markets:
                cat = (m.get("category") or "").lower()
                tags_value = m.get("tags", [])
                if isinstance(tags_value, list):
                    tags = " ".join(str(t) for t in tags_value).lower()
                elif isinstance(tags_value, str):
                    tags = tags_value.lower()
                else:
                    tags = ""
                if any(k in cat or k in tags for k in sports_keywords):
                    continue
                liq = float(m.get("liquidity") or m.get("open_interest") or 0)
                vol = 0.0
                for key in ("volume24h", "volume_24h", "volume24", "volume"):
                    if m.get(key) is not None:
                        try:
                            vol = float(m.get(key))
                        except Exception:
                            vol = 0.0
                        break
                m["_liq_score"] = liq * 0.7 + vol * 0.3
                ranked.append(m)
            markets = sorted(ranked, key=lambda x: x.get("_liq_score", 0), reverse=True)[: top_n]

        count = 0
        with self.db.as_conn() as conn:
            for m in markets:

                # Prefer on-chain condition_id; otherwise fallback to stable slug/question-id for consistent triage
                poll_id = (
                    m.get("condition_id")
                    or m.get("market_slug")
                    or m.get("id")
                    or (m.get("question_id") if m.get("question_id") else None)
                )
                if not poll_id:
                    # As a last resort, build a simple slug from the question text
                    q = (m.get("question") or m.get("title") or "").strip().lower()
                    if not q:
                        continue
                    safe = "".join(ch if ch.isalnum() or ch in "- _" else "-" for ch in q).strip().replace(" ", "-")
                    poll_id = f"q-{safe[:80]}"

                end_ts = int(m.get("_end_ts", 0))

                # Build URL from slug if provided
                market_slug = m.get("market_slug") or m.get("slug")
                url = m.get("url") or (
                    f"https://polymarket.com/event/{market_slug}" if market_slug else f"https://polymarket.com/market/{poll_id}"
                )
                question = (
                    m.get("question")
                    or m.get("title")
                    or m.get("event_title")
                    or m.get("event_name")
                    or m.get("market_question")
                    or "?"
                )
                # Category fallback from tags
                category = m.get("category") or m.get("event_category")
                if not category:
                    tags_value = m.get("tags", [])
                    if isinstance(tags_value, list):
                        # pick first non-generic tag
                        for t in tags_value:
                            if str(t).lower() not in {"all", "elections"}:
                                category = str(t)
                                break
                    elif isinstance(tags_value, str) and tags_value.strip():
                        category = tags_value
                if not category:
                    category = "Unknown"
                status_value = str(m.get("status") or "").lower()
                is_closed_now = bool(m.get("closed", False)) or status_value in {"closed", "resolved", "ended"}
                status = "active" if not is_closed_now else "closed"

                conn.execute(
                    """
                    INSERT INTO polls(poll_id, question, url, category, end_time, status, archived)
                    VALUES(?, ?, ?, ?, ?, ?, 0)
                    ON CONFLICT(poll_id) DO UPDATE SET
                      question=excluded.question,
                      url=excluded.url,
                      category=excluded.category,
                      end_time=excluded.end_time,
                      status=excluded.status
                    """,
                    (poll_id, question, url, category, end_ts, status),
                )

                # Outcomes
                tokens = m.get("tokens") or []
                for t in tokens:
                    outcome_id = t.get("token_id") or t.get("id") or t.get("address")
                    if not outcome_id:
                        continue
                    name = t.get("outcome") or t.get("name") or "?"
                    price = t.get("price")
                    last_price_at = None
                    price_source = "last"

                    conn.execute(
                        """
                        INSERT INTO outcomes(outcome_id, poll_id, name, price, last_price_at, price_source)
                        VALUES(?, ?, ?, ?, ?, ?)
                        ON CONFLICT(outcome_id) DO UPDATE SET
                          poll_id=excluded.poll_id,
                          name=excluded.name,
                          price=excluded.price,
                          last_price_at=excluded.last_price_at,
                          price_source=excluded.price_source
                        """,
                        (outcome_id, poll_id, name, price, last_price_at, price_source),
                    )

                count += 1

        log.info("ingest_complete", extra={"count": count})
        return count


