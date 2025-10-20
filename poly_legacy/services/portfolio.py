"""Portfolio computations for paper trading.

Separates price fetching and sizing logic from the UI so we can later
swap in a real execution layer without refactoring widgets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from ..config import PaperTradingConfig
from ..models import Market, Trade
from ..services.polymarket_client import PolymarketService
from ..storage.trades import TradeRepository


@dataclass
class PortfolioService:
    """Computes balances, stake sizing, and unrealized PnL."""

    trade_repo: TradeRepository
    market_service: PolymarketService
    config: PaperTradingConfig

    async def fetch_active_positions_snapshot(self) -> Tuple[List[Trade], Dict[str, Market]]:
        """Return active trades and a mapping of market_id to current Market."""

        active = self.trade_repo.list_active()
        ids = [t.market_id for t in active]
        if not ids:
            return active, {}
        markets = await self.market_service.fetch_markets_by_ids(ids)
        return active, {m.id: m for m in markets}

    @staticmethod
    def compute_unrealized_pnl(trade: Trade, current_price: float) -> float:
        if trade.entry_odds <= 0:
            return 0.0
        shares = float(trade.stake_amount / trade.entry_odds)
        current_value = shares * float(current_price)
        return float(current_value - trade.stake_amount)

    @staticmethod
    def recommend_stake(cash_available: float, price: float, predicted_prob: float, cap_pct: float) -> float:
        """Capped Kelly based on binary contract price.

        Falls back to 0 if negative and caps to `cap_pct` of bankroll.
        """

        if price <= 0 or price >= 1:
            return 0.0
        b = (1.0 - price) / price
        kelly = ((b * predicted_prob) - (1.0 - predicted_prob)) / b if b > 0 else 0.0
        kelly = max(0.0, min(kelly, cap_pct))
        return round(float(cash_available) * kelly, 2)


