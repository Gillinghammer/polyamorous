from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from py_clob_client.client import ClobClient

from ..config import Config

log = logging.getLogger(__name__)


class PolymarketAPI:
    """Thin wrapper around py-clob-client using the same endpoints as legacy.

    We intentionally use get_sampling_markets() which returns trending/open markets
    suitable for triage, matching the previously working flow.
    """

    def __init__(self, cfg: Config):
        self.clob = ClobClient("https://clob.polymarket.com")

    def get_markets(self) -> List[Dict[str, Any]]:
        try:
            # Use full markets listing to maximize available polls
            payload = self.clob.get_markets()
        except Exception as exc:
            log.error("get_markets_failed", extra={"error": str(exc)})
            raise RuntimeError("Failed to fetch markets from Polymarket CLOB.") from exc

        data = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(data, list):
            log.error("unexpected_markets_shape", extra={"type": type(data).__name__})
            return []
        return data

    def get_orderbook(self, token_id: str) -> Optional[Dict[str, Any]]:
        try:
            return self.clob.get_orderbook(token_id)
        except Exception as exc:  # Fail fast with clear log
            log.error("orderbook_failed", extra={"token_id": token_id, "error": str(exc)})
            return None


