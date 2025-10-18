"""Textual application entry point for Poly."""

from __future__ import annotations

from datetime import datetime, timezone
import asyncio
from typing import Dict, List, Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    LoadingIndicator,
    Markdown,
    ProgressBar,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from .config import AppConfig, load_config
from .models import Market, PortfolioMetrics, ResearchProgress, ResearchResult, Trade
from .services.evaluator import PositionEvaluator
from .services.polymarket_client import PolymarketService
from .services.research import ResearchService
from .storage.trades import TradeRepository


class PolyApp(App):
    """Main Textual application orchestrating the Poly experience."""

    CSS = """
    Screen {
        background: #101217;
    }

    TabbedContent {
        padding: 1 2;
    }

    TabPane {
        padding: 1;
    }

    DataTable#polls-table {
        height: 24;
    }

    Static#polls-hint {
        color: #7a8699;
    }

    RichLog#research-log {
        border: round #2c3340;
        height: 16;
    }

    ProgressBar#research-progress {
        margin-bottom: 1;
    }

    Static#decision-summary {
        height: auto;
        border: round #2c3340;
        padding: 1;
    }

    Horizontal#decision-actions {
        padding-top: 1;
        height: auto;
    }
    
    Horizontal#decision-actions > Button {
        margin-right: 2;
    }

    Static#metrics-summary {
        border: round #2c3340;
        padding: 1;
    }

    DataTable#trades-table {
        height: 14;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "reload_markets", "Refresh Markets"),
    ]

    _markets: reactive[List[Market] | None] = reactive(None)

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        super().__init__()
        self._config = config or load_config()
        self._market_service = PolymarketService(self._config.polls)
        self._research_service = ResearchService(self._config.research)
        self._evaluator = PositionEvaluator(self._config.research)
        self._trade_repository = TradeRepository(self._config.database_path)

        self._active_market: Optional[Market] = None
        self._research_result: Optional[ResearchResult] = None
        self._evaluation = None

    def compose(self) -> ComposeResult:
        """Build the UI layout."""

        yield Header(show_clock=True)
        with TabbedContent(initial="polls"):
            with TabPane("Polls", id="polls"):
                yield DataTable(id="polls-table", zebra_stripes=True)
                yield Static("Select a poll and press Enter to start research.", id="polls-hint")
            with TabPane("Research", id="research"):
                yield Static("No poll selected", id="research-title")
                yield ProgressBar(total=4, id="research-progress")
                yield LoadingIndicator(id="research-spinner")
                yield RichLog(id="research-log")
            with TabPane("Decision", id="decision"):
                yield Markdown("Awaiting research results...", id="decision-summary")
                with Horizontal(id="decision-actions"):
                    yield Button("Enter Trade", id="enter-trade", variant="primary", disabled=True)
                    yield Button("Pass", id="pass-trade", variant="warning", disabled=True)
            with TabPane("Dashboard", id="dashboard"):
                with Vertical():
                    yield Static("Loading portfolio metrics...", id="metrics-summary")
                    trades_table = DataTable(id="trades-table", zebra_stripes=True)
                    trades_table.add_columns("ID", "Question", "Side", "Odds", "Status", "PnL")
                    yield trades_table
        yield Footer()

    def on_mount(self) -> None:
        """Initialize UI state once the app is ready."""

        table = self.query_one("#polls-table", DataTable)
        table.add_columns("Question", "Options", "Current Odds", "Time Left", "Liquidity")
        table.cursor_type = "row"
        self.load_markets()
        self.refresh_dashboard()
        # Hide spinner initially (Textual: set display property after mount)
        spinner = self.query_one("#research-spinner", LoadingIndicator)
        spinner.display = False

    @work(exclusive=True)
    async def load_markets(self) -> None:
        """Background task to fetch markets and populate the table."""

        table = self.query_one("#polls-table", DataTable)
        table.clear()
        hint = self.query_one("#polls-hint", Static)
        hint.update("Loading latest markets...")
        markets = await self._market_service.fetch_top_markets()
        self._markets = markets
        for market in markets:
            odds = ", ".join(
                f"{name} {price:.0%}" for name, price in market.formatted_odds().items()
            )
            options = "/".join(outcome.outcome for outcome in market.outcomes)
            time_left = _format_timedelta(market.time_remaining)
            liquidity = f"${market.liquidity:,.0f}"
            table.add_row(
                market.question,
                options,
                odds,
                time_left,
                liquidity,
                key=market.id,
            )
        hint.update("Select a poll and press Enter to start research.")
        self.notify(f"Loaded {len(markets)} markets", title="Markets Updated")

    @work(exclusive=True)
    async def refresh_dashboard(self) -> None:
        """Update dashboard metrics in the background."""

        # This worker is async and runs in the app's loop; update directly
        metrics = self._trade_repository.metrics()
        self._render_dashboard(metrics)

    def _render_dashboard(self, metrics: PortfolioMetrics) -> None:
        summary = (
            f"Active Positions: {metrics.active_positions}\n"
            f"Win Rate: {metrics.win_rate:.1%}\n"
            f"Total Profit: ${metrics.total_profit:,.2f}\n"
            f"Average Profit: ${metrics.average_profit:,.2f}\n"
            f"Projected APR: {metrics.projected_apr:.1%}"
        )
        summary_widget = self.query_one("#metrics-summary", Static)
        summary_widget.update(summary)

        table = self.query_one("#trades-table", DataTable)
        table.clear()
        for trade in metrics.recent_trades:
            profit = "-" if trade.profit_loss is None else f"${trade.profit_loss:,.2f}"
            table.add_row(
                str(trade.id),
                trade.question[:50] + ("…" if len(trade.question) > 50 else ""),
                trade.selected_option,
                f"{trade.entry_odds:.0%}",
                trade.status.capitalize(),
                profit,
            )

    @on(DataTable.RowSelected, "#polls-table")
    def handle_market_selected(self, event: DataTable.RowSelected) -> None:
        """Trigger research when a market row is chosen."""

        market = self._find_market(event.row_key.value)
        if market is None:
            return

        self._active_market = market
        self.query_one(TabbedContent).active = "research"

        title = self.query_one("#research-title", Static)
        title.update(f"Researching: {market.question}")
        progress = self.query_one("#research-progress", ProgressBar)
        progress.update(progress=0, total=4)
        spinner = self.query_one("#research-spinner", LoadingIndicator)
        spinner.display = True
        log = self.query_one("#research-log", RichLog)
        log.clear()

        self._research_result = None
        self._evaluation = None
        self.run_research()

    @work(exclusive=True, thread=True)
    def run_research(self) -> None:
        """Execute the research workflow for the active market in a dedicated thread."""

        market = self._active_market
        if market is None:
            return

        def callback(progress: ResearchProgress) -> None:
            # Crossing thread boundary – schedule UI update safely
            self.call_from_thread(self._handle_progress_update, progress)

        def _run() -> None:
            try:
                result = asyncio.run(self._research_service.conduct_research(market, callback))
                evaluation = self._evaluator.evaluate(market, result)
                self.call_from_thread(self._handle_research_complete, result, evaluation)
            except BaseException:
                import traceback
                tb = traceback.format_exc()
                def _fail() -> None:
                    log = self.query_one("#research-log", RichLog)
                    log.write("Error during research:\n" + tb)
                    spinner = self.query_one("#research-spinner", LoadingIndicator)
                    spinner.display = False
                    self.notify("Research failed", title="Grok Error")
                self.call_from_thread(_fail)

        _run()

    def _handle_progress_update(self, progress: ResearchProgress) -> None:
        log = self.query_one("#research-log", RichLog)
        log.write(progress.message)
        bar = self.query_one("#research-progress", ProgressBar)
        bar.update(progress=progress.round_number, total=progress.total_rounds)
        if progress.completed:
            spinner = self.query_one("#research-spinner", LoadingIndicator)
            spinner.display = False

    def _handle_research_complete(self, result: ResearchResult, evaluation) -> None:
        self._research_result = result
        self._evaluation = evaluation

        spinner = self.query_one("#research-spinner", LoadingIndicator)
        spinner.display = False

        summary = self._build_decision_markdown(result, evaluation)
        summary_widget = self.query_one("#decision-summary", Markdown)
        summary_widget.update(summary)

        enter_button = self.query_one("#enter-trade", Button)
        pass_button = self.query_one("#pass-trade", Button)

        enter_button.disabled = False
        pass_button.disabled = False

        if evaluation.recommendation == "enter":
            enter_button.variant = "primary"
            enter_button.tooltip = "Research indicates sufficient edge to enter."
        else:
            enter_button.variant = "default"
            enter_button.tooltip = "Recommendation is to pass; enter only if you disagree."

        self.query_one(TabbedContent).active = "decision"
        self.notify("Research complete", title="Decision Ready")

    def _build_decision_markdown(self, result: ResearchResult, evaluation) -> str:
        findings = "\n".join(f"- {finding}" for finding in result.key_findings)
        citations = "\n".join(f"- {citation}" for citation in result.citations)
        recommendation = "Enter position" if evaluation.recommendation == "enter" else "Pass"
        return (
            f"### Recommendation: {recommendation}\n"
            f"**Predicted Outcome:** {result.prediction} ({result.probability:.0%})\n\n"
            f"**Confidence:** {result.confidence:.0f}%\n\n"
            f"**Edge vs Market:** {evaluation.edge:+.2f}\n\n"
            f"**Rationale:** {evaluation.rationale}\n\n"
            f"**Key Findings**\n{findings}\n\n"
            f"**Citations**\n{citations}"
        )

    @on(Button.Pressed, "#enter-trade")
    def handle_enter_trade(self, event: Button.Pressed) -> None:
        if not self._active_market or not self._research_result:
            return

        market = self._active_market
        result = self._research_result

        odds = market.formatted_odds().get(result.prediction, 0.5)
        trade = Trade(
            id=None,
            market_id=market.id,
            question=market.question,
            selected_option=result.prediction,
            entry_odds=odds,
            stake_amount=self._config.paper_trading.default_stake,
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
        stored = self._trade_repository.record_trade(trade)
        self.notify(f"Recorded paper trade #{stored.id}", title="Trade Entered")
        self.refresh_dashboard()

    @on(Button.Pressed, "#pass-trade")
    def handle_pass_trade(self, event: Button.Pressed) -> None:
        self.notify("Passed on trade", title="Decision Logged")

    def action_reload_markets(self) -> None:
        self.load_markets()

    def _find_market(self, market_id: str) -> Optional[Market]:
        if not self._markets:
            return None
        return next((market for market in self._markets if market.id == market_id), None)


def _format_timedelta(delta) -> str:
    """Pretty print time remaining."""

    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
