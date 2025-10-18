from __future__ import annotations

import json
import csv
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlmodel import select

from .config import CONFIG_PATH, Settings, load_settings
from .logging import configure_logging
from .models.db import Market, Position, Proposal, Research, Trade
from .services.calculations import evaluate_market, recommend_stake
from .services.persistence import get_engine, init_db, session_scope, upsert_markets
from .services.polymarket import PolymarketClient
from .services.research import ResearchOrchestrator
from .tui.views import display_review, display_scan

app = typer.Typer(help="CLI Market Analyst for Polymarket")
console = Console()


@app.callback()
def main(ctx: typer.Context, config: Optional[Path] = typer.Option(None, help="Path to config.yml")):
    """Initialize configuration and database before commands run."""

    configure_logging()
    settings = load_settings(config)
    ctx.obj = {
        "settings": settings,
        "engine": get_engine(),
        "config_path": config or CONFIG_PATH,
    }
    init_db(ctx.obj["engine"])


def _load_markets(settings: Settings):
    client = PolymarketClient(settings)
    return client.filtered_markets()


def _persist_markets(engine, markets: Iterable):
    if not markets:
        return
    with session_scope(engine) as session:
        upsert_markets(session, markets)
        session.commit()


@app.command()
def scan(ctx: typer.Context):
    """Scan and display candidate Polymarket markets."""

    settings: Settings = ctx.obj["settings"]
    markets = _load_markets(settings)
    _persist_markets(ctx.obj["engine"], markets)
    if not markets:
        typer.echo("No markets met the configured filters.")
        return
    display_scan(console, markets)


@app.command()
def review(ctx: typer.Context, market_id: str = typer.Argument(..., help="Target market identifier")):
    """Run research on a market and present results."""

    settings: Settings = ctx.obj["settings"]
    engine = ctx.obj["engine"]
    markets = _load_markets(settings)
    _persist_markets(engine, markets)
    if not markets:
        typer.echo("No markets met the configured filters. Run `pm scan` first.")
        raise typer.Exit(code=1)
    selected = next((m for m in markets if m.id == market_id), None)
    if not selected:
        typer.echo(f"Market {market_id} not found in filtered list.")
        raise typer.Exit(code=1)

    orchestrator = ResearchOrchestrator(settings)
    result = orchestrator.run_research(selected.id, selected.question)
    edge_report = evaluate_market(result.probability_yes, selected.prices, selected.resolves_at)
    display_review(console, markets, selected, edge_report, result.rationale, result.citations, result.confidence)

    with session_scope(engine) as session:
        research = Research(
            market_id=selected.id,
            probability_yes=result.probability_yes,
            confidence=result.confidence,
            rationale=result.rationale,
            citations=json.dumps(result.citations),
            rounds=result.rounds,
        )
        session.add(research)
        session.commit()

        disqualifications = []
        if result.confidence < settings.research.min_confidence:
            disqualifications.append(
                f"confidence {result.confidence:.0%} below minimum {settings.research.min_confidence:.0%}"
            )
        if edge_report.edge < settings.research.min_edge:
            disqualifications.append(
                f"edge {edge_report.edge:+.2%} below minimum {settings.research.min_edge:.0%}"
            )
        if edge_report.roi <= 0:
            disqualifications.append("negative expected ROI")

        if disqualifications:
            console.print(
                Panel(
                    "\n".join(disqualifications),
                    title="No proposal generated",
                    border_style="red",
                )
            )
            typer.echo(f"Stored research #{research.id} without proposal.")
            return

        stake = recommend_stake(
            settings.sizing.policy,
            settings.sizing.bankroll,
            settings.sizing.risk_budget,
            result.confidence,
            edge_report.roi,
            settings.sizing.max_fraction,
        )
        if stake <= 0:
            console.print(Panel("Stake rounded to zero; proposal skipped.", border_style="red"))
            typer.echo(f"Stored research #{research.id} without proposal.")
            return

        proposal = Proposal(
            market_id=selected.id,
            side=edge_report.side,
            stake=stake,
            edge=edge_report.edge,
            apr=edge_report.apr,
            risk_free_apr=settings.risk_free_apr,
            accepted=False,
            research_id=research.id,
        )
        session.add(proposal)
        session.commit()
        typer.echo(f"Stored research #{research.id} and proposal #{proposal.id} for {selected.slug}.")


@app.command()
def accept(
    ctx: typer.Context,
    market_id: str = typer.Argument(..., help="Market id"),
    stake: Optional[float] = typer.Option(None, help="Override stake amount"),
    side: Optional[str] = typer.Option(None, help="Override side", case_sensitive=False),
):
    """Accept latest proposal for a market, optionally overriding stake/side."""

    engine = ctx.obj["engine"]
    settings: Settings = ctx.obj["settings"]
    with session_scope(engine) as session:
        proposal = session.exec(
            select(Proposal).where(Proposal.market_id == market_id).order_by(Proposal.created_at.desc())
        ).first()
        if not proposal:
            typer.echo("No proposal found. Run review first.")
            raise typer.Exit(code=1)

        if side:
            proposal.side = side.lower()
        if stake is not None:
            if stake <= 0:
                typer.echo("Stake must be positive.")
                raise typer.Exit(code=1)
            proposal.stake = stake
        proposal.accepted = True
        session.add(proposal)

        market: Market | None = session.get(Market, proposal.market_id)
        entry_price = 1.0
        if market:
            entry_price = market.price_yes if proposal.side == "yes" else market.price_no
        else:
            fallback = next((m for m in _load_markets(settings) if m.id == proposal.market_id), None)
            if fallback:
                entry_price = fallback.prices.get(proposal.side, entry_price)

        trade = Trade(
            market_id=proposal.market_id,
            side=proposal.side,
            stake=proposal.stake,
            entry_price=entry_price,
            research_id=proposal.research_id,
        )
        session.add(trade)

        existing_position = session.exec(
            select(Position).where(Position.market_id == proposal.market_id, Position.status == "open")
        ).first()
        if existing_position:
            total_stake = existing_position.stake + proposal.stake
            if total_stake > 0:
                weighted_entry = (
                    existing_position.entry_price * existing_position.stake
                    + entry_price * proposal.stake
                ) / total_stake
                existing_position.entry_price = weighted_entry
            existing_position.stake = total_stake
            existing_position.mark_price = entry_price
            existing_position.side = proposal.side
            session.add(existing_position)
        else:
            session.add(
                Position(
                    market_id=proposal.market_id,
                    side=proposal.side,
                    stake=proposal.stake,
                    entry_price=entry_price,
                    mark_price=entry_price,
                    unrealized_pnl=0.0,
                )
            )
        session.commit()
        typer.echo(f"Accepted proposal #{proposal.id}; recorded trade #{trade.id}.")


@app.command()
def positions(ctx: typer.Context):
    """Display open positions with unrealized P&L."""

    engine = ctx.obj["engine"]
    with session_scope(engine) as session:
        rows = session.exec(select(Position).where(Position.status == "open")).all()
        markets: Dict[str, Market] = {m.id: m for m in session.exec(select(Market)).all()}
    if not rows:
        typer.echo("No open positions yet.")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Market")
    table.add_column("Side")
    table.add_column("Stake")
    table.add_column("Entry")
    table.add_column("Mark")
    table.add_column("UPnL")
    total_stake = 0.0
    total_upnl = 0.0
    for row in rows:
        total_stake += row.stake
        total_upnl += row.unrealized_pnl
        market = markets.get(row.market_id)
        table.add_row(
            market.slug if market else row.market_id,
            row.side,
            f"${row.stake:,.2f}",
            f"{row.entry_price:.2f}",
            f"{row.mark_price:.2f}",
            f"${row.unrealized_pnl:,.2f}",
        )
    table.add_section()
    table.add_row("TOTAL", "", f"${total_stake:,.2f}", "", "", f"${total_upnl:,.2f}")
    console.print(table)


@app.command()
def history(ctx: typer.Context, csv_path: Optional[Path] = typer.Option(None, help="Export path")):
    """Show trade history or export to CSV."""

    engine = ctx.obj["engine"]
    with session_scope(engine) as session:
        trades = session.exec(select(Trade).order_by(Trade.timestamp.desc())).all()
        markets: Dict[str, Market] = {m.id: m for m in session.exec(select(Market)).all()}

    if not trades:
        typer.echo("No trades recorded yet.")
        return

    if csv_path:
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["id", "market", "side", "stake", "entry_price", "timestamp"])
            for trade in trades:
                market = markets.get(trade.market_id)
                writer.writerow(
                    [
                        trade.id,
                        market.slug if market else trade.market_id,
                        trade.side,
                        f"{trade.stake:.2f}",
                        f"{trade.entry_price:.2f}",
                        trade.timestamp.isoformat(),
                    ]
                )
        typer.echo(f"Exported {len(trades)} trades to {csv_path}")
    else:
        table = Table(show_header=True, header_style="bold")
        table.add_column("ID")
        table.add_column("Market")
        table.add_column("Side")
        table.add_column("Stake")
        table.add_column("Entry")
        table.add_column("Timestamp")
        for trade in trades:
            market = markets.get(trade.market_id)
            table.add_row(
                str(trade.id),
                market.slug if market else trade.market_id,
                trade.side,
                f"${trade.stake:,.2f}",
                f"{trade.entry_price:.2f}",
                trade.timestamp.strftime("%Y-%m-%d %H:%M"),
            )
        console.print(table)


@app.command()
def settings(ctx: typer.Context):
    """Print resolved configuration."""

    settings: Settings = ctx.obj["settings"]
    payload = {
        "risk_free_apr": settings.risk_free_apr,
        "risk_free_provider": settings.risk_free_provider,
        "liquidity": asdict(settings.liquidity),
        "research": asdict(settings.research),
        "sizing": asdict(settings.sizing),
        "updates": asdict(settings.updates),
        "xai_api_key": "set" if settings.xai_api_key else "missing",
        "config_path": str(ctx.obj["config_path"]),
    }
    console.print_json(data=payload)


def run():
    app()


__all__ = ["app", "run"]
