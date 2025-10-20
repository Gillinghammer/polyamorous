from __future__ import annotations

from ..services.portfolio import PortfolioService
from ..storage.trades import TradeRepository
from ..models import Trade, Market, ResearchResult
from datetime import datetime, timezone


class PortfolioController:
    def __init__(self, portfolio: PortfolioService, trades: TradeRepository) -> None:
        self._portfolio = portfolio
        self._trades = trades

    async def refresh_snapshot(self):
        return await self._portfolio.fetch_active_positions_snapshot()

    def close_trade(self, trade_id: int, exit_price: float) -> None:
        self._trades.close_trade(trade_id, exit_price)

    def enter_trade(self, market: Market, result: ResearchResult, stake: float, research_repo=None) -> Trade:
        odds = market.formatted_odds().get(result.prediction, 0.5)
        trade = Trade(
            id=None,
            market_id=market.id,
            question=market.question,
            category=market.category,
            selected_option=result.prediction,
            entry_odds=odds,
            stake_amount=float(stake),
            entry_timestamp=datetime.now(tz=timezone.utc),
            predicted_probability=result.probability,
            confidence=result.confidence,
            research_id=None,
            status="active",
            resolves_at=market.end_date,
            actual_outcome=None,
            profit_loss=None,
            closed_at=None,
        )
        stored = self._trades.record_trade(trade)
        if research_repo is not None:
            try:
                research_repo.set_decision(market.id, "enter")
            except Exception:
                pass
        return stored

    def pass_trade(self, research_repo, market_id: str) -> None:
        try:
            research_repo.set_decision(market_id, "pass")
        except Exception:
            pass

    async def exit_trade_by_id(self, trade_id: int) -> bool:
        """Close a trade at current market price using portfolio snapshot."""
        active, markets_by_id = await self._portfolio.fetch_active_positions_snapshot()
        trade = next((t for t in active if t.id == trade_id), None)
        if not trade:
            return False
        market = markets_by_id.get(trade.market_id)
        if not market:
            return False
        current = float(market.formatted_odds().get(trade.selected_option, 0.0))
        self._trades.close_trade(trade.id, current)
        return True

    def set_active_flag_for_market(self, research_view, market_id: str | None) -> None:
        if not market_id:
            try:
                research_view.set_active_flag(False)
            except Exception:
                pass
            return
        latest = self._trades.find_latest_by_market(market_id)
        try:
            research_view.set_active_flag(bool(latest and latest.status == "active"))
        except Exception:
            pass


