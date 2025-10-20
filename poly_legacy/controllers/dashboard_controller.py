from __future__ import annotations

from typing import Dict, List, Tuple

from ..models import PortfolioMetrics, Trade, Market
from ..utils import format_timedelta


class DashboardController:
    def build_summary(self, metrics: PortfolioMetrics, spend: float) -> str:
        return (
            f"Active Positions: {metrics.active_positions}\n"
            f"Win Rate: {metrics.win_rate:.1%}\n"
            f"Largest Win: ${metrics.largest_win:,.2f}   Largest Loss: ${metrics.largest_loss:,.2f}\n"
            f"Best Category: {metrics.best_category or '-'}   Worst Category: {metrics.worst_category or '-'}\n"
            f"Total Profit: ${metrics.total_profit:,.2f}\n"
            f"Average Profit: ${metrics.average_profit:,.2f}\n"
            f"Cash Available: ${metrics.cash_available:,.2f}   In Play: ${metrics.cash_in_play:,.2f}\n"
            f"Projected APR: {metrics.projected_apr:.1%}\n"
            f"Research Spend (this session): ${spend:,.4f}"
        )

    def build_active_rows(
        self,
        active_trades: List[Trade],
        markets_by_id: Dict[str, Market],
        compute_unrealized,
    ) -> List[Tuple[str, ...]]:
        rows: List[Tuple[str, ...]] = []
        for trade in active_trades:
            market = markets_by_id.get(trade.market_id)
            current = 0.0
            time_left = "-"
            if market:
                current = float(market.formatted_odds().get(trade.selected_option, 0.0))
                time_left = format_timedelta(market.time_remaining)
            unreal = compute_unrealized(trade, current)
            rows.append(
                (
                    str(trade.id),
                    trade.question[:50] + ("…" if len(trade.question) > 50 else ""),
                    trade.selected_option,
                    f"{trade.entry_odds:.0%}",
                    f"{current:.0%}",
                    f"${unreal:,.2f}",
                    time_left,
                    str(trade.id),
                )
            )
        return rows


