from __future__ import annotations

import asyncio
# Textual worker decorator import removed; using asyncio tasks directly

from ..models import Market, ResearchProgress, ResearchResult
from ..services.research import ResearchService
from ..services.evaluator import PositionEvaluator
from ..messages import ResearchProgressMsg, ResearchCompleteMsg, ResearchFailedMsg
from ..utils import build_citations_md


class ResearchController:
    """Runs research workflow and emits Textual messages.

    This controller is intentionally light; the App should be the message bus.
    """

    def __init__(self, service: ResearchService, evaluator: PositionEvaluator, post_message) -> None:
        self._service = service
        self._evaluator = evaluator
        self._post = post_message  # typically app.post_message

    def start(self, market: Market) -> None:
        """Start research in the background for a market."""

        async def _run() -> None:
            def _cb(progress: ResearchProgress) -> None:
                self._post(ResearchProgressMsg(market.id, progress))

            try:
                result = await self._service.conduct_research(market, _cb)
                evaluation = self._evaluator.evaluate(market, result)
                self._post(ResearchCompleteMsg(market.id, result, evaluation))
            except Exception as exc:  # noqa: BLE001
                self._post(ResearchFailedMsg(market.id, str(exc)))

        # Fire and forget; the App manages lifecycle
        asyncio.create_task(_run())

    def hydrate_and_render(
        self,
        *,
        market: Market,
        state,
        research_repo,
        trade_repo,
        portfolio_service,
        paper_config,
        research_view,
    ) -> None:
        result: ResearchResult | None = state.research_results_by_market.get(market.id)
        evaluation = state.evaluations_by_market.get(market.id)
        if not result and not evaluation:
            persisted = research_repo.get_by_market_id(market.id)
            if persisted:
                res, edge, rec = persisted
                state.research_results_by_market[market.id] = res
                class _Eval:
                    def __init__(self, edge, recommendation) -> None:
                        self.edge = edge
                        self.recommendation = recommendation
                        self.rationale = "Loaded from storage"
                state.evaluations_by_market[market.id] = _Eval(edge, rec)
                result = res
                evaluation = state.evaluations_by_market[market.id]
        if result and evaluation:
            metrics = trade_repo.metrics(paper_config.starting_cash)
            price = market.formatted_odds().get(result.prediction, 0.5)
            try:
                rec_size = portfolio_service.recommend_stake(
                    metrics.cash_available,
                    price,
                    result.probability,
                    paper_config.max_risk_per_trade_pct,
                )
            except Exception:
                rec_size = 0.0
            state.entry_stake_by_market[market.id] = rec_size
            try:
                research_view.render_result(result, evaluation)
                research_view.set_decision_band(float(evaluation.edge))
                shares = (rec_size / price) if price > 0 else 0.0
                projected_win = (shares * 1.0) - rec_size
                research_view.update_info_chips(float(price), float(rec_size), float(shares), float(projected_win))
                research_view.set_enter_labels(float(rec_size), float(projected_win))
                web_count, x_count, md = build_citations_md(result.citations)
                research_view.update_citations(web_count, x_count, md)
            except Exception:
                pass

    def tick_progress(self, state, on_tick) -> None:
        updated = False
        for market_id, running in list(state.research_running.items()):
            if not running:
                continue
            current = int(state.progress_pct_by_market.get(market_id, 0))
            if current < 95:
                state.progress_pct_by_market[market_id] = min(95, current + 1)
                updated = True
        if updated:
            try:
                on_tick()
            except Exception:
                pass

    async def open_from_history(self, market_id: str, *, market_service, app_open_fn) -> None:
        """Fetch a market (if needed) then delegate to app's open function."""
        market = None
        try:
            market = await market_service.fetch_market_by_id(market_id)
        except Exception:
            market = None
        if market is not None:
            app_open_fn(market)
