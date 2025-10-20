"""Textual application entry point for Poly."""

from __future__ import annotations

from datetime import datetime, timezone
import asyncio
from typing import Dict, List, Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    LoadingIndicator,
    Markdown,
    ProgressBar,
    Static,
    TabbedContent,
    TabPane,
)

from .config import AppConfig, load_config
from .models import Market, PortfolioMetrics, ResearchProgress, ResearchResult, Trade
from .services.evaluator import PositionEvaluator
from .services.polymarket_client import PolymarketService
from .services.portfolio import PortfolioService
from .services.research import ResearchService
from .storage.trades import TradeRepository
from .storage.research import ResearchRepository
from .ui.styles import CSS as UI_CSS
from .ui.polls_view import PollsView
from .ui.research_view import ResearchView
from .ui.dashboard_view import DashboardView
from .controllers.research_controller import ResearchController
from .controllers.portfolio_controller import PortfolioController
from .controllers.polls_controller import PollsController
from .controllers.dashboard_controller import DashboardController
from .controllers.research_history_controller import ResearchHistoryController
from .controllers.hotkey_controller import HotkeyController
from .messages import ResearchProgressMsg, ResearchCompleteMsg, ResearchFailedMsg, PollSelectedMsg, TradeSelectedMsg
from .utils import format_timedelta, build_citations_md
from .controllers.state import AppState


class PolyApp(App):
    """Main Textual application orchestrating the Poly experience."""

    CSS = UI_CSS

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "reload_markets", "Refresh Markets"),
        ("g", "refresh_portfolio", "Refresh Portfolio"),
        ("x", "exit_position", "Exit Position"),
        ("u", "toggle_history_undecided", "Undecided History"),
        ("c", "toggle_citations", "Citations"),
        ("z", "toggle_logs", "Logs"),
        ("i", "toggle_edge_help", "Edge Help"),
        # Sorting
        ("l", "sort_liquidity", "Sort Liquidity"),
        ("t", "sort_time", "Sort Time"),
        ("v", "sort_volume", "Sort Volume"),
        # Day filters
        ("1", "days_7", "<=7d"),
        ("2", "days_14", "<=14d"),
        ("3", "days_30", "<=30d"),
        ("4", "days_60", "<=60d"),
        ("5", "days_90", "<=90d"),
        ("6", "days_365", "<=365d"),
        ("0", "days_clear", "Clear Days"),
        # Filters
        ("f", "toggle_researched", "Filter Researched"),
    ]

    _markets: reactive[List[Market] | None] = reactive(None)

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        super().__init__()
        self._config = config or load_config()
        self._market_service = PolymarketService(self._config.polls)
        self._research_service = ResearchService(self._config.research)
        self._evaluator = PositionEvaluator(self._config.research)
        self._trade_repository = TradeRepository(self._config.database_path)
        self._research_repository = ResearchRepository(self._config.database_path)
        self._portfolio = PortfolioService(self._trade_repository, self._market_service, self._config.paper_trading)
        # Controllers
        self._research_controller = ResearchController(self._research_service, self._evaluator, self.post_message)
        self._portfolio_controller = PortfolioController(self._portfolio, self._trade_repository)
        self._polls_controller = PollsController(self._research_repository, self._trade_repository)
        self._dashboard_controller = DashboardController()
        self._history_controller = ResearchHistoryController()
        self._hotkey_controller = HotkeyController(self)

        self._active_market: Optional[Market] = None
        self._state = AppState()
        # Per-market state for concurrent research and persistence
        self._research_running: Dict[str, bool] = {}
        self._progress_by_market: Dict[str, ResearchProgress] = {}
        self._research_results_by_market: Dict[str, ResearchResult] = {}
        self._evaluations_by_market: Dict[str, object] = {}
        self._logs_by_market: Dict[str, List[str]] = {}
        self._progress_pct_by_market: Dict[str, int] = {}
        self._current_page: int = 1
        self._page_size: int = int(self._config.polls.top_n)
        self._day_filter: Optional[int] = None
        self._category_filter: Optional[str] = None
        self._sort_key: str = "liquidity"
        self._filter_researched: bool = False
        self._research_history_filter: str = "all"
        self._selected_trade_id: Optional[int] = None
        self._entry_stake_by_market: Dict[str, float] = {}
        self._history_row_index_by_id: Dict[str, int] = {}
        self._question_by_market_id: Dict[str, str] = {}

    def compose(self) -> ComposeResult:
        """Build the UI layout."""

        yield Header(show_clock=True)
        with TabbedContent(initial="polls"):
            with TabPane("Polls", id="polls"):
                yield PollsView()
            with TabPane("Research", id="research"):
                yield ResearchView()
            with TabPane("Dashboard", id="dashboard"):
                yield DashboardView()
        yield Footer()

    def on_mount(self) -> None:
        """Initialize UI state once the app is ready."""

        # Set cursors within views
        try:
            self.query_one("#polls-table", DataTable).cursor_type = "row"
            self.query_one("#trades-table", DataTable).cursor_type = "row"
            self.query_one("#research-history", DataTable).cursor_type = "row"
        except Exception:
            pass
        # Cache view references
        try:
            self._research_view = self.query_one(ResearchView)
        except Exception:
            self._research_view = None
        self.load_markets()
        self.refresh_dashboard()
        try:
            self._render_research_history(self._research_history_filter)
        except Exception:
            pass
        # View initializes its own visibility state
        # (Removed legacy research log auto-scroll)
        # Periodic tick to smooth progress percentages in Polls view
        try:
            self.set_interval(1.0, lambda: self._research_controller.tick_progress(self._state, self._render_polls_table))
        except Exception:
            pass

    @work(exclusive=True)
    async def load_markets(self) -> None:
        """Background task to fetch markets and populate the table."""

        # Build rows and hand to PollsView
        hint = self.query_one("#polls-hint", Static)
        hint.update("Loading latest markets...")
        try:
            markets = await self._market_service.fetch_all_markets()
        except Exception:
            markets = await self._market_service.fetch_markets_page(self._current_page, self._page_size)
        self._markets = markets
        # Map ids to readable questions for research history fallback
        try:
            self._state.question_by_market_id = {m.id: m.question for m in markets}
        except Exception:
            self._state.question_by_market_id = {}
        self._render_polls_table()
        # Refresh research history with loaded market questions
        try:
            self._render_research_history(self._research_history_filter)
        except Exception:
            pass
        hint.update("Select a poll and press Enter to start research. Select again to open details.")
        self.notify(f"Loaded {len(markets)} markets", title="Markets Updated")
        

    def _render_polls_table(self) -> None:
        """Render the polls table with research/trade status."""

        if not self._markets:
            return
        markets = self._polls_controller.apply_filters_and_sort(
            self._markets,
            self._sort_key,
            self._day_filter,
            self._category_filter,
        )
        rows = self._polls_controller.build_rows(
            markets,
            self._state.research_running,
            self._state.progress_pct_by_market,
            self._state.research_results_by_market,
            self._state.evaluations_by_market,
        )
        try:
            self.query_one(PollsView).update_rows(rows)
        except Exception:
            pass

    # Polls cells are built in PollsController

    @work(exclusive=True)
    async def refresh_dashboard(self) -> None:
        """Update dashboard metrics in the background."""

        # This worker is async and runs in the app's loop; update directly
        metrics = self._trade_repository.metrics(self._config.paper_trading.starting_cash)
        active, markets_by_id = await self._portfolio.fetch_active_positions_snapshot()
        self._render_dashboard(metrics, active, markets_by_id)

    def _render_dashboard(self, metrics: PortfolioMetrics, active_trades: Optional[List[Trade]] = None, markets_by_id: Optional[Dict[str, Market]] = None) -> None:
        # Compute research spend from results we tracked in-session
        spend = 0.0
        try:
            for res in self._research_results_by_market.values():
                if res and res.estimated_cost_usd:
                    spend += float(res.estimated_cost_usd)
        except Exception:
            spend = 0.0

        summary = self._dashboard_controller.build_summary(metrics, spend)
        try:
            self.query_one(DashboardView).update_summary(summary)
        except Exception:
            pass

        if active_trades is None or markets_by_id is None:
            active_trades = []
            markets_by_id = {}
        rows = self._dashboard_controller.build_active_rows(
            active_trades,
            markets_by_id,
            self._portfolio.compute_unrealized_pnl,
        )
        try:
            self.query_one(DashboardView).update_active_trades(rows)
        except Exception:
            pass

    @on(PollSelectedMsg)
    def handle_market_selected(self, event: PollSelectedMsg) -> None:
        """Start or open research when a market row is chosen."""

        market = self._find_market(event.market_id)
        if market is None:
            return

        # If already persisted or running, open details; otherwise start in background
        already_persisted = self._research_repository.has_research(market.id)
        if already_persisted or self._research_running.get(market.id):
            self._open_research_details(market)
            return

        # Start background research, keep user on Polls
        self._state.progress_by_market[market.id] = ResearchProgress(message="Starting…", round_number=0, total_rounds=int(self._config.research.default_rounds))
        self._state.research_running[market.id] = True
        self._state.logs_by_market.setdefault(market.id, [])
        self._state.progress_pct_by_market[market.id] = 0
        self._render_polls_table()
        self.notify("Research started", title="Grok")
        self.run_research_for_market(market)

    def run_research_for_market(self, market: Market) -> None:
        """Kick off research via the controller; non-blocking."""
        self._research_controller.start(market)

    # Message handlers from controller
    @on(ResearchProgressMsg)
    def _on_research_progress_msg(self, msg: ResearchProgressMsg) -> None:
        self._handle_progress_update_for_market(msg.market_id, msg.progress)

    @on(ResearchCompleteMsg)
    def _on_research_complete_msg(self, msg: ResearchCompleteMsg) -> None:
        self._handle_research_complete_for_market(msg.market_id, msg.result, msg.evaluation)

    @on(ResearchFailedMsg)
    def _on_research_failed_msg(self, msg: ResearchFailedMsg) -> None:
        market_id = msg.market_id
        # Clean running flags and notify
        self._state.research_running.pop(market_id, None)
        self._state.progress_by_market.pop(market_id, None)
        self._render_polls_table()
        if self._active_market and self._active_market.id == market_id:
            try:
                spinner = self.query_one("#research-spinner", LoadingIndicator)
                spinner.display = False
            except Exception:
                pass
        self.notify("Research failed", title="Grok Error")

    def _handle_progress_update_for_market(self, market_id: str, progress: ResearchProgress) -> None:
        # Store progress and append logs
        self._state.progress_by_market[market_id] = progress
        self._state.logs_by_market.setdefault(market_id, []).append(progress.message)
        # Update smoothed percent and polls table status
        if not progress.completed:
            pct_from_rounds = int(100 * (progress.round_number / max(progress.total_rounds, 1))) if progress.total_rounds else 0
            prev = int(self._state.progress_pct_by_market.get(market_id, 0))
            # Smoothly tick forward but cap at 95% until completion
            smooth = min(max(prev + 3, pct_from_rounds), 95)
            self._state.progress_pct_by_market[market_id] = smooth
        else:
            self._state.progress_pct_by_market[market_id] = 100
        # Update polls table status
        self._render_polls_table()
        # If the details view is open for this market, update widgets
        if self._active_market and self._active_market.id == market_id:
            try:
                self._research_view.update_progress(progress)  # type: ignore[attr-defined]
            except Exception:
                pass

    def _handle_research_complete_for_market(self, market_id: str, result: ResearchResult, evaluation) -> None:
        # Save state and persist
        self._state.research_running.pop(market_id, None)
        self._state.research_results_by_market[market_id] = result
        self._state.evaluations_by_market[market_id] = evaluation
        try:
            self._research_repository.upsert_result(result, evaluation.edge, evaluation.recommendation)
        except Exception:
            # Non-fatal persistence error; surface but continue
            import traceback
            self.notify("Failed to persist research", title="Storage Error")

        # Update polls table
        self._render_polls_table()

        # If viewing this market, update the details pane
        if self._active_market and self._active_market.id == market_id:
            try:
                self._research_view.render_result(result, evaluation)  # type: ignore[attr-defined]
                self._research_view.set_decision_band(float(evaluation.edge))  # type: ignore[attr-defined]
            except Exception:
                pass
            # Stats row via view
            try:
                if self._active_market:
                    self._research_view.render_stats(self._active_market, result)  # type: ignore[attr-defined]
            except Exception:
                pass
            # Citations counts and list
            try:
                web_count, x_count, md = build_citations_md(result.citations)
                self._research_view.update_citations(web_count, x_count, md)  # type: ignore[attr-defined]
            except Exception:
                pass
        # (Decision band style applied via ResearchView)
        # Update trade preview and button label via view
        try:
            self._update_trade_preview(self._active_market, result)
        except Exception:
            pass
        self.notify("Research complete", title="Decision Ready")

    # (Citations helper moved to utils.build_citations_md)

    # (Moved stat chip construction into ResearchView.render_stats)

    # (Decision band styling moved to ResearchView.set_decision_band)

    @on(Button.Pressed, "#enter-trade")
    def handle_enter_trade(self, event: Button.Pressed) -> None:
        if not self._active_market:
            return
        market = self._active_market
        result = self._state.research_results_by_market.get(market.id)
        if not result:
            return
        stake = float(self._state.entry_stake_by_market.get(market.id, self._config.paper_trading.default_stake))
        stored = self._portfolio_controller.enter_trade(market, result, stake, research_repo=self._research_repository)
        self.notify(f"Recorded paper trade #{stored.id}", title="Trade Entered")
        self.refresh_dashboard()
        self._render_polls_table()
        try:
            self._research_view.set_active_flag(True)  # type: ignore[attr-defined]
        except Exception:
            pass

    @on(Button.Pressed, "#pass-trade")
    def handle_pass_trade(self, event: Button.Pressed) -> None:
        if not self._active_market:
            return
        self._portfolio_controller.pass_trade(self._research_repository, self._active_market.id)
        self._render_polls_table()
        self.notify("Passed on trade", title="Decision Logged")

    def action_reload_markets(self) -> None:
        self.load_markets()

    @work(exclusive=True)
    async def action_refresh_portfolio(self) -> None:
        """Refresh active prices and dashboard metrics."""
        # Fetch snapshot (connectivity) and refresh dashboard
        try:
            await self._portfolio_controller.refresh_snapshot()
        except Exception:
            pass
        await self.refresh_dashboard()
        # Update active flag via controller helper
        try:
            self._portfolio_controller.set_active_flag_for_market(self._research_view, self._active_market.id if self._active_market else None)
        except Exception:
            pass

    def action_toggle_history_undecided(self) -> None:
        self._hotkey_controller.handle_toggle_history_undecided()

    def action_toggle_citations(self) -> None:
        self._hotkey_controller.handle_toggle_citations()

    def action_toggle_logs(self) -> None:
        self._hotkey_controller.handle_toggle_logs()

    def action_toggle_edge_help(self) -> None:
        self._hotkey_controller.handle_toggle_edge_help()

    @on(TradeSelectedMsg)
    def handle_trade_selected(self, event: TradeSelectedMsg) -> None:
        try:
            self._selected_trade_id = int(event.trade_id)
        except Exception:
            self._selected_trade_id = None

    @on(DataTable.RowSelected, "#research-history")
    def handle_history_selected(self, event: DataTable.RowSelected) -> None:
        market_id = str(event.row_key.value)
        self.open_market_from_history(market_id)

    @work(exclusive=True)
    async def open_market_from_history(self, market_id: str) -> None:
        market = self._find_market(market_id)
        if market is None:
            await self._research_controller.open_from_history(market_id, market_service=self._market_service, app_open_fn=self._open_research_details)
            return
        self._open_research_details(market)

    @work(exclusive=True)
    async def action_exit_position(self) -> None:
        """Exit the selected active position at current price (paper)."""
        if not self._selected_trade_id:
            return
        try:
            ok = await self._portfolio_controller.exit_trade_by_id(self._selected_trade_id)
            self.notify("Position closed" if ok else "Trade not found", title="Paper Trade")
        except Exception:
            self.notify("Failed to close position", title="Storage Error")
        await self.refresh_dashboard()

    # Sorting & Quick filter actions
    def action_sort_liquidity(self) -> None:
        self._hotkey_controller.handle_sort_liquidity()

    def action_sort_time(self) -> None:
        self._hotkey_controller.handle_sort_time()

    def action_sort_volume(self) -> None:
        self._hotkey_controller.handle_sort_volume()

    def action_days_7(self) -> None:
        self._hotkey_controller.handle_days_filter(7)

    def action_days_14(self) -> None:
        self._hotkey_controller.handle_days_filter(14)

    def action_days_30(self) -> None:
        self._hotkey_controller.handle_days_filter(30)

    def action_days_60(self) -> None:
        self._hotkey_controller.handle_days_filter(60)

    def action_days_90(self) -> None:
        self._hotkey_controller.handle_days_filter(90)

    def action_days_365(self) -> None:
        self._hotkey_controller.handle_days_filter(365)

    def action_days_clear(self) -> None:
        self._hotkey_controller.handle_days_filter(None)

    def action_category_clear(self) -> None:
        self._hotkey_controller.handle_category_clear()

    def action_toggle_researched(self) -> None:
        self._hotkey_controller.handle_toggle_researched()

    def _find_market(self, market_id: str) -> Optional[Market]:
        if not self._markets:
            return None
        return next((market for market in self._markets if market.id == market_id), None)

    def _open_research_details(self, market: Market) -> None:
        """Populate and show the Research tab for a market without starting it (if already running/done)."""
        self._active_market = market
        self.query_one(TabbedContent).active = "research"
        try:
            self._research_view.set_market(market)  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            self._research_controller.hydrate_and_render(
                market=market,
                state=self._state,
                research_repo=self._research_repository,
                trade_repo=self._trade_repository,
                portfolio_service=self._portfolio,
                paper_config=self._config.paper_trading,
                research_view=self._research_view,
            )
        except Exception:
            pass

    def _render_research_history(self, filter_mode: str = "all") -> None:
        rows = self._research_repository.list(filter_mode)
        q_by_id = {m.id: m.question for m in (self._markets or [])}
        q_by_id.update(self._state.question_by_market_id)
        view_rows: list[tuple[str, ...]] = self._history_controller.build_history_rows(rows, q_by_id)
        try:
            self._research_view.update_history(view_rows)  # type: ignore[attr-defined]
            if rows and not self._active_market:
                self._research_view.highlight_history_row(0)  # type: ignore[attr-defined]
                awaitable = self.open_market_from_history(rows[0]["market_id"])  # type: ignore[index]
        except Exception:
            pass
