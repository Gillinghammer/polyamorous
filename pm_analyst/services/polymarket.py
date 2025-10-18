from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List

from ..config import Settings
from ..utils.paths import data_path


@dataclass
class MarketData:
    id: str
    slug: str
    question: str
    resolves_at: datetime
    prices: dict[str, float]
    volume_24h: float
    open_interest: float
    top_of_book_depth: float
    category: str
    volatility_hint: float

    @property
    def time_to_expiry_hours(self) -> float:
        return max((self.resolves_at - datetime.now(timezone.utc)).total_seconds() / 3600, 0.0)


class PolymarketClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def load_markets(self) -> List[MarketData]:
        with data_path("sample_markets.json").open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        markets = []
        for item in raw:
            markets.append(
                MarketData(
                    id=item["id"],
                    slug=item["slug"],
                    question=item["question"],
                    resolves_at=datetime.fromisoformat(item["resolves_at"].replace("Z", "+00:00")),
                    prices=item["prices"],
                    volume_24h=item["volume_24h"],
                    open_interest=item["open_interest"],
                    top_of_book_depth=item["top_of_book_depth"],
                    category=item["category"],
                    volatility_hint=item.get("volatility_hint", 0.0),
                )
            )
        return markets

    def filtered_markets(self) -> List[MarketData]:
        settings = self.settings
        candidates: Iterable[MarketData] = self.load_markets()
        filtered: List[MarketData] = []
        for market in candidates:
            if market.open_interest < settings.liquidity.min_oi:
                continue
            if market.volume_24h < settings.liquidity.min_vol24h:
                continue
            if market.top_of_book_depth < settings.liquidity.min_depth:
                continue
            filtered.append(market)
        return sorted(filtered, key=self._score_market, reverse=True)

    @staticmethod
    def _score_market(market: MarketData) -> float:
        time_weight = max(market.time_to_expiry_hours / 24, 0)
        return market.open_interest / 100_000 + market.volume_24h / 10_000 + time_weight + market.volatility_hint


__all__ = ["PolymarketClient", "MarketData"]
