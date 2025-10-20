from __future__ import annotations

from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, LoadingIndicator, Markdown, ProgressBar, Static
from textual import on

from ..models import Market, ResearchProgress, ResearchResult
from ..utils import format_timedelta


class ResearchView(Horizontal):
    """Composable Research view widget with left/right panels.

    Exposes minimal methods called by the App or controllers.
    """

    def __init__(self) -> None:
        super().__init__()

    def compose(self):  # type: ignore[override]
        with Vertical(id="research-left"):
            with VerticalScroll(id="research-scroll"):
                # Single clean header with poll title and status
                yield Static("No poll selected", id="research-title")
                yield Static("", id="research-status")
                
                # Progress indicator (hidden when not running)
                yield ProgressBar(total=4, id="research-progress")
                yield LoadingIndicator(id="research-spinner")
                
                # Main decision container with all key info
                with Vertical(id="decision-container"):
                    # Recommendation headline
                    yield Markdown("Awaiting recommendation…", id="decision-summary")
                    
                    # Key metrics in a clean grid
                    with Horizontal(id="metrics-grid"):
                        yield Static("Price: -", id="metric-price")
                        yield Static("Model: -", id="metric-model") 
                        yield Static("Edge: -", id="metric-edge")
                        yield Static("Confidence: -", id="metric-confidence")
                        yield Static("Time Left: -", id="metric-time")
                    
                    # Position sizing info
                    with Horizontal(id="position-info"):
                        yield Static("Recommended Stake: -", id="position-stake")
                        yield Static("Potential Win: -", id="position-win")
                        yield Static("", id="active-status")
                    
                    # Action buttons (only show if recommendation is enter)
                    with Horizontal(id="action-buttons"):
                        yield Button("Enter Position", id="enter-trade", variant="primary", disabled=True)
                        yield Button("Pass", id="pass-trade", variant="warning", disabled=True)
                
                # Research details
                yield Markdown("Awaiting research results...", id="research-summary")
                yield Static("", id="citations-header")
                yield Markdown("", id="citations-list")
                yield Static("Edge (EV per $1) = model probability − market price. Positive = favorable; Breakeven = price.", id="edge-help")
        with Vertical(id="research-right"):
            table = DataTable(id="research-history", zebra_stripes=True)
            table.add_columns("Polls", "Rec", "Decision", "Edge", "Date")
            yield table

    # No-op helpers that App can call in future; kept for interface stability
    def set_market(self, market: Market) -> None:
        self.query_one("#research-title", Static).update(market.question)
        # Reset progress visuals for new market
        try:
            bar = self.query_one("#research-progress", ProgressBar)
            bar.update(progress=0, total=bar.total or 4)
            bar.display = False
            self.query_one("#research-status", Static).update("")
            self.query_one("#research-spinner", LoadingIndicator).display = False
            self.query_one("#decision-summary", Markdown).update("Awaiting recommendation…")
            self.query_one("#research-summary", Markdown).update("Awaiting research results...")
            # Reset metrics
            self.query_one("#metric-price", Static).update("Price: -")
            self.query_one("#metric-model", Static).update("Model: -")
            self.query_one("#metric-edge", Static).update("Edge: -")
            self.query_one("#metric-confidence", Static).update("Confidence: -")
            self.query_one("#metric-time", Static).update("Time Left: -")
            self.query_one("#position-stake", Static).update("Recommended Stake: -")
            self.query_one("#position-win", Static).update("Potential Win: -")
            self.query_one("#active-status", Static).update("")
        except Exception:
            pass

    def update_progress(self, p: ResearchProgress) -> None:
        bar = self.query_one("#research-progress", ProgressBar)
        bar.update(progress=p.round_number, total=p.total_rounds)
        bar.display = True
        status = self.query_one("#research-status", Static)
        status.update(f"{int(100 * (p.round_number / max(p.total_rounds, 1)))}%" if not p.completed else "")
        if p.completed:
            try:
                self.query_one("#research-spinner", LoadingIndicator).display = False
                bar.display = False
            except Exception:
                pass

    def render_result(self, res: ResearchResult, evaluation) -> None:
        # Headline + details
        self.query_one("#decision-summary", Markdown).update(
            f"### {'✅ Enter' if evaluation.recommendation=='enter' else '🚫 Pass'}\n{evaluation.rationale}"
        )
        # Update research summary with actual results
        self.query_one("#research-summary", Markdown).update(res.summary)
        # Buttons visibility
        enter = self.query_one("#enter-trade", Button)
        ps = self.query_one("#pass-trade", Button)
        if evaluation.recommendation == "enter":
            enter.display = True
            ps.display = True
            enter.disabled = False
            ps.disabled = False
        else:
            enter.display = False
            ps.display = False
        # Citations header remains updated by app; ensure spinner/progress hidden
        try:
            self.query_one("#research-spinner", LoadingIndicator).display = False
            self.query_one("#research-progress", ProgressBar).display = False
            self.query_one("#research-status", Static).update("")
        except Exception:
            pass

    def update_info_chips(self, price: float, stake: float, payout: float, profit: float) -> None:
        # Update individual metric displays
        try:
            self.query_one("#metric-price", Static).update(f"Price: {price:.0%}")
            self.query_one("#position-stake", Static).update(f"Recommended Stake: ${stake:,.2f}")
            self.query_one("#position-win", Static).update(f"Potential Win: ${profit:,.2f}")
        except Exception:
            pass

    def set_decision_band(self, edge: float) -> None:
        try:
            container = self.query_one("#decision-container", Vertical)
            edge_widget = self.query_one("#metric-edge", Static)
            edge_widget.update(f"Edge: {edge:+.2f}")
        except Exception:
            return
        for cls in ("enter", "neutral", "pass"):
            if container.has_class(cls):
                container.remove_class(cls)
        if edge > 0.02:
            container.add_class("enter")
        elif edge < -0.02:
            container.add_class("pass")
        else:
            container.add_class("neutral")

    def update_citations(self, web_count: int, x_count: int, markdown_list: str) -> None:
        try:
            header = self.query_one("#citations-header", Static)
            header.update(f"Citations: {web_count} websites 🌐, {x_count} posts 𝕩 [ press c to toggle]")
            self.query_one("#citations-list", Markdown).update(markdown_list)
        except Exception:
            pass

    def set_enter_labels(self, stake: float, profit: float) -> None:
        try:
            label = f"Enter Position — ${stake:,.2f} (+${profit:,.2f})"
            self.query_one("#enter-trade", Button).label = label
        except Exception:
            pass

    def set_active_flag(self, active: bool) -> None:
        try:
            self.query_one("#active-status", Static).update("[Active]" if active else "")
        except Exception:
            pass

    def update_history(self, rows: list[tuple[str, ...]]) -> None:
        """Populate right-side history: (question, rec, decision, edge, date, market_id)."""
        table = self.query_one("#research-history", DataTable)
        table.clear()
        for row in rows:
            *cells, market_id = row
            table.add_row(*cells, key=market_id)

    def highlight_history_row(self, index: int) -> None:
        try:
            table = self.query_one("#research-history", DataTable)
            table.cursor_coordinate = (index, 0)
        except Exception:
            pass

    def render_stats(self, market: Market, result: ResearchResult) -> None:
        """Update all metric displays with computed values."""
        try:
            price = float(market.formatted_odds().get(result.prediction, 0.0))
        except Exception:
            price = 0.0
        edge = float(result.probability - price)
        time_left = format_timedelta(market.time_remaining)

        # Update individual metric widgets
        self.query_one("#metric-price", Static).update(f"Price: {price:.0%}")
        self.query_one("#metric-model", Static).update(f"Model: {result.probability:.0%}")
        self.query_one("#metric-edge", Static).update(f"Edge: {edge:+.2f}")
        self.query_one("#metric-confidence", Static).update(f"Confidence: {result.confidence:.0f}%")
        self.query_one("#metric-time", Static).update(f"Time Left: {time_left}")


