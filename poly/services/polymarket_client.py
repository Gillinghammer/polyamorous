"""Client wrapper for fetching Polymarket markets."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module, util
from typing import Iterable, List

from ..config import PollConfig
from ..models import Market, MarketOutcome


HOST = "https://clob.polymarket.com"


@dataclass
class PolymarketService:
    """Service responsible for fetching and formatting markets."""

    poll_config: PollConfig

    def __post_init__(self) -> None:
        self._client = self._create_client()

    async def fetch_top_markets(self) -> List[Market]:
        """Fetch the top configured markets, falling back to offline samples."""

        return await asyncio.to_thread(self._fetch_markets_sync)

    def _create_client(self):
        """Instantiate the py_clob_client if available."""

        if util.find_spec("py_clob_client.client") is None:
            return None

        module = import_module("py_clob_client.client")
        client = getattr(module, "ClobClient")(HOST)
        return client

    def _fetch_markets_sync(self) -> List[Market]:
        """Blocking market fetch implementation."""

        markets: List[Market]
        if self._client is None:
            raise RuntimeError("py-clob-client not installed; live markets required per no-fallback rule.")
        # Single canonical endpoint for live markets
        raw = self._client.get_sampling_markets()
        raw_markets: Iterable[dict] = raw.get("data", []) if isinstance(raw, dict) else raw
        markets = self._transform_markets(raw_markets)

        return markets[: self.poll_config.top_n]

    def _transform_markets(self, raw_markets: Iterable[dict]) -> List[Market]:
        """Convert raw markets to domain objects using configured filters."""

        now = datetime.now(tz=timezone.utc)
        active: list[dict] = []
        for market in raw_markets:
            if not isinstance(market, dict):
                continue
            if market.get("archived", False):
                continue
            end_iso = market.get("end_date_iso") or market.get("game_start_time")
            if not end_iso:
                continue
            try:
                end_dt = datetime.fromisoformat(str(end_iso).replace("Z", "+00:00"))
            except Exception:
                continue
            if end_dt <= now:
                continue
            # Require at least 1 outcome token with a price
            tokens = market.get("tokens", []) or []
            if not tokens:
                continue
            active.append(market)

        exclude_tokens = {category.lower() for category in self.poll_config.exclude_categories}
        filtered = [
            market
            for market in active
            if not _is_sports_market(market, exclude_tokens)
        ]

        for market in filtered:
            market["liquidity_score"] = self._liquidity_score(market)

        sorted_markets = sorted(
            filtered,
            key=lambda m: m.get("liquidity_score", 0.0),
            reverse=True,
        )

        return [self._convert_market(market) for market in sorted_markets]

    def _liquidity_score(self, market: dict) -> float:
        """Calculate liquidity score using config weights."""

        # Polymarket payloads may use various keys; normalize with sensible fallbacks
        open_interest = float(
            market.get("liquidity")
            or market.get("open_interest")
            or market.get("oi")
            or 0.0
        )
        volume = float(
            market.get("volume")
            or market.get("volume24")
            or market.get("volume24h")
            or market.get("volume_24h")
            or 0.0
        )
        return (
            open_interest * self.poll_config.liquidity_weight_open_interest
            + volume * self.poll_config.liquidity_weight_volume_24h
        )

    def _convert_market(self, market: dict) -> Market:
        """Map dictionary structure into our Market dataclass."""

        # Resolution / end time
        end_date_iso = market.get("end_date_iso") or market.get("game_start_time")
        end_date = datetime.fromisoformat(str(end_date_iso).replace("Z", "+00:00"))
        outcomes = [
            MarketOutcome(
                token_id=token["token_id"],
                outcome=token.get("outcome", ""),
                price=float(token.get("price", 0.0)),
                winner=token.get("winner"),
            )
            for token in market.get("tokens", [])
        ]
        return Market(
            id=market["condition_id"],
            question=market.get("question", ""),
            description=market.get("description", ""),
            category=market.get("category", "Unknown"),
            liquidity=float(
                market.get("liquidity") or market.get("open_interest") or 0.0
            ),
            volume_24h=float(
                market.get("volume")
                or market.get("volume24h")
                or market.get("volume24")
                or 0.0
            ),
            end_date=end_date,
            outcomes=outcomes,
            tags=[tag for tag in market.get("tags", [])],
        )


def _is_sports_market(market: dict, excluded: set[str]) -> bool:
    """Return True if market belongs to an excluded category."""

    category = str(market.get("category", "")).lower()
    if any(token in category for token in excluded):
        return True

    tags = " ".join(market.get("tags", [])).lower()
    return any(token in tags for token in excluded)


def _offline_markets() -> Iterable[Market]:
    """Provide deterministic sample markets when offline."""

    now = datetime.now(tz=timezone.utc)
    sample = [
        Market(
            id="sample-1",
            question="Will the Senate pass the climate bill by Q4?",
            description="Tracking legislative progress on the pending climate bill.",
            category="Politics",
            liquidity=1_250_000.0,
            volume_24h=250_000.0,
            end_date=now.replace(month=12, day=31, hour=23, minute=59),
            outcomes=[
                MarketOutcome(token_id="sample-1-yes", outcome="Yes", price=0.58),
                MarketOutcome(token_id="sample-1-no", outcome="No", price=0.42),
            ],
            tags=["politics", "legislation"],
        ),
        Market(
            id="sample-2",
            question="Will global AI investment exceed $250B in 2025?",
            description="Assesses total capital deployment into AI companies.",
            category="Economics",
            liquidity=980_000.0,
            volume_24h=190_000.0,
            end_date=now.replace(year=2026, month=1, day=15, hour=12, minute=0),
            outcomes=[
                MarketOutcome(token_id="sample-2-yes", outcome="Yes", price=0.47),
                MarketOutcome(token_id="sample-2-no", outcome="No", price=0.53),
            ],
            tags=["economics", "technology"],
        ),
    ]
    return sample
