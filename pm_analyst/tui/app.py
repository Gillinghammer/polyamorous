from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, OptionList, Static
from sqlmodel import select

from ..config import Settings, load_settings
from ..logging import configure_logging
from ..models.db import Market, Position, Proposal, Research, Trade
from ..services.persistence import get_engine, init_db, session_scope
from ..services.workflows import ResearchOutcome, accept_latest_proposal, load_filtered_markets, run_research_flow


MENU_COMMANDS = (
    ("/get polls", "polls"),
    ("/get positions", "positions"),
    ("/get bets", "bets"),
    ("/get research", "research"),
)


@dataclass
class TableView:
    columns: List[str]
    rows: List[List[str]]
    keys: Optional[List[str]] = None


class PolyDashboard(App):
    """Full-screen dashboard for managing Polymarket research flows."""

    CSS_PATH = "poly.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("/", "focus_menu", "Commands"),
        Binding("a", "accept_recommendation", "Accept", show=False),
        Binding("r", "reject_recommendation", "Reject", show=False),
    ]

    current_view = reactive("dashboard")

    def __init__(self, config_path: Optional[Path] = None) -> None:
        super().__init__()
        configure_logging()
        self.settings = load_settings(config_path)
        self.engine = get_engine()
        init_db(self.engine)
        self.markets = []
        self.pending_outcome: Optional[ResearchOutcome] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Static("POLY", id="logo")
                yield Static("Loading account summary...", id="summary")
                menu = OptionList(id="menu")
                for label, value in MENU_COMMANDS:
                    menu.add_option(OptionList.Option(label, id=value))
                yield menu
            with Vertical(id="main-area"):
                yield Static("Welcome to Poly Analyst", id="title")
                table = DataTable(id="table")
                table.cursor_type = "row"
                table.zebra_stripes = True
                yield table
                yield Static(Panel("Select a command from the menu to begin.", title="Status"), id="detail")
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_summary()
        self.focus_menu()

    def focus_menu(self) -> None:
        self.query_one(OptionList).focus()

    async def action_focus_menu(self) -> None:
        self.focus_menu()

    async def refresh_summary(self) -> None:
        summary_widget = self.query_one("#summary", Static)
        summary = await asyncio.to_thread(self.build_summary_text)
        summary_widget.update(summary)

    def build_summary_text(self) -> Panel:
        with session_scope(self.engine) as session:
            positions = session.exec(select(Position).where(Position.status == "open")).all()
            proposals = session.exec(select(Proposal).where(Proposal.accepted == False)).all()
            researches = session.exec(select(Research)).all()
            trades = session.exec(select(Trade)).all()

        total_stake = sum(p.stake for p in positions)
        total_upnl = sum(p.unrealized_pnl for p in positions)
        summary_table = Table.grid(padding=(0, 1))
        summary_table.add_row("Open Positions", f"{len(positions)} | ${total_stake:,.2f}")
        summary_table.add_row("Unrealized PnL", f"${total_upnl:,.2f}")
        summary_table.add_row("Active Proposals", str(len(proposals)))
        summary_table.add_row("Research Reports", str(len(researches)))
        summary_table.add_row("Recorded Bets", str(len(trades)))
        return Panel(summary_table, title="Account", border_style="#00e5ff")

    def clear_table(self) -> DataTable:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        return table

    def update_table(self, view: TableView) -> None:
        table = self.clear_table()
        table.cursor_type = "row"
        if not view.columns:
            return
        table.add_columns(*view.columns)
        if view.rows:
            for idx, row in enumerate(view.rows):
                key = view.keys[idx] if view.keys else str(idx)
                table.add_row(*row, key=key)
            table.focus()
        else:
            table.cursor_type = "cell"
        table.refresh()

    def update_detail(self, message: Panel) -> None:
        self.query_one("#detail", Static).update(message)

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        command = event.option.id
        if command == "polls":
            await self.action_get_polls()
        elif command == "positions":
            await self.action_get_positions()
        elif command == "bets":
            await self.action_get_bets()
        elif command == "research":
            await self.action_get_research()

    async def action_get_polls(self) -> None:
        self.current_view = "polls"
        self.update_detail(Panel("Fetching polls...", title="Status"))
        markets = await asyncio.to_thread(load_filtered_markets, self.settings, self.engine)
        self.markets = markets
        if not markets:
            self.update_table(TableView(columns=["Message"], rows=[["No markets met liquidity preferences."]]))
            self.update_detail(Panel("No markets met the configured filters.", title="Polls", border_style="red"))
            return
        rows = [
            [
                market.slug,
                market.category,
                market.resolves_at.strftime("%Y-%m-%d"),
                f"{market.prices['yes']:.2f}",
                f"{market.prices['no']:.2f}",
                f"${market.open_interest:,.0f}",
            ]
            for market in markets
        ]
        keys = [market.id for market in markets]
        columns = ["Slug", "Category", "Resolve", "YES", "NO", "Open Interest"]
        self.update_table(TableView(columns=columns, rows=rows, keys=keys))
        self.update_detail(
            Panel("Select a poll to run research. Press A to accept or R to reject recommendations.", title="Polls")
        )
        await self.refresh_summary()

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self.current_view != "polls":
            return
        market_id = str(event.row_key.value)
        market = next((m for m in self.markets if m.id == market_id), None)
        if not market:
            self.update_detail(Panel("Selected poll is no longer available.", title="Polls", border_style="red"))
            return
        self.update_detail(Panel(f"Running research for {market.slug}...", title="Research"))
        outcome = await asyncio.to_thread(run_research_flow, self.engine, self.settings, market)
        self.pending_outcome = outcome
        self.update_detail(self.render_research_detail(outcome))
        await self.refresh_summary()

    def render_research_detail(self, outcome: ResearchOutcome) -> Panel:
        body = Text(justify="left")
        body.append(f"Probability YES: {outcome.result.probability_yes:.2f}\n", style="bold")
        body.append(f"Confidence: {outcome.result.confidence:.0%}\n")
        body.append(f"Edge: {outcome.edge_report.edge:+.2%}\n")
        body.append(f"ROI: {outcome.edge_report.roi:+.2%}\n")
        body.append(f"APR: {outcome.edge_report.apr:+.2f}\n\n")
        body.append("Rationale:\n", style="bold")
        body.append(outcome.result.rationale)
        if outcome.result.citations:
            body.append("\n\nCitations:\n", style="bold")
            for idx, citation in enumerate(outcome.result.citations, start=1):
                body.append(f"[{idx}] {citation}\n", style="dim")
        if outcome.disqualifications:
            body.append("\n\nNo proposal generated:\n", style="bold red")
            for item in outcome.disqualifications:
                body.append(f"- {item}\n")
        elif outcome.proposal:
            body.append("\nRecommendation:\n", style="bold")
            body.append(
                f"Stake ${outcome.proposal.stake:,.2f} on {outcome.proposal.side.upper()}\n",
                style="green",
            )
            body.append("Press A to accept or R to reject this recommendation.")
        return Panel(body, title=outcome.market.question, border_style="#00e5ff")

    async def action_get_positions(self) -> None:
        self.current_view = "positions"
        with session_scope(self.engine) as session:
            rows = session.exec(select(Position).where(Position.status == "open")).all()
            markets: Dict[str, Market] = {m.id: m for m in session.exec(select(Market)).all()}
        if not rows:
            self.update_table(TableView(columns=["Message"], rows=[["No open positions yet."]]))
            self.update_detail(Panel("No open positions to display.", title="Positions"))
            return
        table_rows = [
            [
                markets.get(row.market_id).slug if row.market_id in markets else row.market_id,
                row.side,
                f"${row.stake:,.2f}",
                f"{row.entry_price:.2f}",
                f"{row.mark_price:.2f}",
                f"${row.unrealized_pnl:,.2f}",
            ]
            for row in rows
        ]
        columns = ["Market", "Side", "Stake", "Entry", "Mark", "UPnL"]
        self.update_table(TableView(columns=columns, rows=table_rows))
        self.update_detail(Panel("Current open positions and unrealized PnL.", title="Positions"))
        await self.refresh_summary()

    async def action_get_bets(self) -> None:
        self.current_view = "bets"
        with session_scope(self.engine) as session:
            trades = session.exec(select(Trade).order_by(Trade.timestamp.desc())).all()
            markets: Dict[str, Market] = {m.id: m for m in session.exec(select(Market)).all()}
        if not trades:
            self.update_table(TableView(columns=["Message"], rows=[["No historical bets found."]]))
            self.update_detail(Panel("No bets recorded yet.", title="Bets"))
            return
        rows = [
            [
                str(trade.id),
                markets.get(trade.market_id).slug if trade.market_id in markets else trade.market_id,
                trade.side,
                f"${trade.stake:,.2f}",
                f"{trade.entry_price:.2f}",
                trade.timestamp.strftime("%Y-%m-%d %H:%M"),
            ]
            for trade in trades
        ]
        columns = ["ID", "Market", "Side", "Stake", "Entry", "Timestamp"]
        self.update_table(TableView(columns=columns, rows=rows))
        self.update_detail(Panel("Historical bets and execution details.", title="Bets"))
        await self.refresh_summary()

    async def action_get_research(self) -> None:
        self.current_view = "research"
        with session_scope(self.engine) as session:
            researches = session.exec(select(Research).order_by(Research.created_at.desc())).all()
            proposals = {p.research_id: p for p in session.exec(select(Proposal)).all()}
            markets: Dict[str, Market] = {m.id: m for m in session.exec(select(Market)).all()}
        if not researches:
            self.update_table(TableView(columns=["Message"], rows=[["No research reports stored yet."]]))
            self.update_detail(Panel("Run research on a poll to see it here.", title="Research"))
            return
        rows = []
        for research in researches:
            market = markets.get(research.market_id)
            proposal = proposals.get(research.id)
            status = "No proposal"
            if proposal:
                status = "Accepted" if proposal.accepted else "Pending"
            rows.append(
                [
                    str(research.id),
                    market.slug if market else research.market_id,
                    research.created_at.strftime("%Y-%m-%d %H:%M"),
                    f"{research.probability_yes:.2f}",
                    f"{research.confidence:.0%}",
                    status,
                ]
            )
        columns = ["ID", "Market", "Created", "P(YES)", "Confidence", "Status"]
        self.update_table(TableView(columns=columns, rows=rows))
        self.update_detail(Panel("Stored research rounds and proposal status.", title="Research"))
        await self.refresh_summary()

    async def action_accept_recommendation(self) -> None:
        if not self.pending_outcome or not self.pending_outcome.proposal:
            self.update_detail(Panel("No recommendation ready to accept.", title="Research", border_style="red"))
            return
        try:
            outcome = await asyncio.to_thread(
                accept_latest_proposal,
                self.engine,
                self.settings,
                self.pending_outcome.proposal.market_id,
                None,
                None,
            )
        except ValueError as exc:
            self.update_detail(Panel(str(exc), title="Research", border_style="red"))
            return
        self.pending_outcome = None
        message = Panel(
            f"Accepted proposal #{outcome.proposal.id}; recorded trade #{outcome.trade.id}.",
            title="Accepted",
            border_style="green",
        )
        self.update_detail(message)
        await self.refresh_summary()
        if self.current_view == "positions":
            await self.action_get_positions()
        elif self.current_view == "bets":
            await self.action_get_bets()
        elif self.current_view == "research":
            await self.action_get_research()

    async def action_reject_recommendation(self) -> None:
        if not self.pending_outcome or not self.pending_outcome.proposal:
            self.update_detail(Panel("No recommendation ready to reject.", title="Research", border_style="red"))
            return
        proposal_id = self.pending_outcome.proposal.id
        with session_scope(self.engine) as session:
            proposal = session.get(Proposal, proposal_id)
            if proposal:
                proposal.accepted = False
                session.add(proposal)
                session.commit()
        self.pending_outcome = None
        self.update_detail(
            Panel("Recommendation rejected and left pending in the queue.", title="Rejected", border_style="yellow")
        )
        await self.refresh_summary()
        if self.current_view == "research":
            await self.action_get_research()


def run(config_path: Optional[Path] = None) -> None:
    app = PolyDashboard(config_path)
    app.run()


__all__ = ["PolyDashboard", "run"]
