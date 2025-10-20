from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..models import Market
from ..storage.research import ResearchRepository
from ..storage.trades import TradeRepository
from ..utils import format_timedelta


class PollsController:
    def __init__(self, research_repo: ResearchRepository, trade_repo: TradeRepository) -> None:
        self._research_repo = research_repo
        self._trade_repo = trade_repo

    def apply_filters_and_sort(
        self,
        markets: List[Market],
        sort_key: str,
        day_filter: Optional[int],
        category_filter: Optional[str],
    ) -> List[Market]:
        filtered = markets
        if category_filter:
            wanted = category_filter.lower()
            filtered = [m for m in filtered if str(m.category or "").lower() == wanted]
        if day_filter is not None:
            from datetime import timedelta
            max_delta = timedelta(days=int(day_filter))
            filtered = [m for m in filtered if m.time_remaining <= max_delta]
        if sort_key == "liquidity":
            filtered.sort(key=lambda m: (m.liquidity or 0.0), reverse=True)
        elif sort_key == "time":
            filtered.sort(key=lambda m: m.time_remaining)
        elif sort_key == "volume":
            filtered.sort(key=lambda m: (m.volume_24h or 0.0), reverse=True)
        return filtered

    def build_rows(
        self,
        markets: List[Market],
        research_running: Dict[str, bool],
        progress_pct_by_market: Dict[str, int],
        research_results_by_market: Dict[str, object],
        evaluations_by_market: Dict[str, object],
    ) -> List[Tuple[str, ...]]:
        rows: List[Tuple[str, ...]] = []
        for market in markets:
            odds = ", ".join(f"{name} {price:.0%}" for name, price in market.formatted_odds().items())
            options = "/".join(outcome.outcome for outcome in market.outcomes)
            time_left = format_timedelta(market.time_remaining)
            volume = f"${market.volume_24h:,.0f}" if market.volume_24h else "-"
            research_cell, rec_cell = self._research_cells_for_market(
                market.id,
                research_running,
                progress_pct_by_market,
                research_results_by_market,
                evaluations_by_market,
            )
            trade_cell = self._trade_cell_for_market(market.id)
            rows.append(
                (
                    market.question,
                    options,
                    odds,
                    time_left,
                    volume,
                    research_cell,
                    rec_cell,
                    trade_cell,
                    market.id,
                )
            )
        return rows

    def _research_cells_for_market(
        self,
        market_id: str,
        research_running: Dict[str, bool],
        progress_pct_by_market: Dict[str, int],
        research_results_by_market: Dict[str, object],
        evaluations_by_market: Dict[str, object],
    ) -> tuple[str, str]:
        if research_running.get(market_id):
            pct = int(progress_pct_by_market.get(market_id, 0))
            return (f"🧪 {pct}%", "…")
        persisted = self._research_repo.get_by_market_id(market_id)
        result = research_results_by_market.get(market_id)
        evaluation = evaluations_by_market.get(market_id)
        if persisted or (result and evaluation):
            rec = (
                getattr(evaluations_by_market.get(market_id), "recommendation", None)
                if evaluations_by_market.get(market_id)
                else "pass"
            )
            return ("✅ Done", "Enter" if rec == "enter" else "Pass")
        return ("Start (Enter)", "-")

    def _trade_cell_for_market(self, market_id: str) -> str:
        trade = self._trade_repo.find_latest_by_market(market_id)
        if not trade:
            return "-"
        return trade.status.capitalize()


