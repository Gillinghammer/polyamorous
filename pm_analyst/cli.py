from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import select

from .config import CONFIG_PATH, Settings, load_settings
from .logging import configure_logging
from .models.db import Position, Proposal, Research, Trade
from .services.calculations import evaluate_market, recommend_stake
from .services.persistence import get_engine, init_db, session_scope
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
    }
    init_db(ctx.obj["engine"])


def _load_markets(settings: Settings):
    client = PolymarketClient(settings)
    return client.filtered_markets()


@app.command()
def scan(ctx: typer.Context):
    """Scan and display candidate Polymarket markets."""

    settings: Settings = ctx.obj["settings"]
    markets = _load_markets(settings)
    display_scan(console, markets)


@app.command()
def review(ctx: typer.Context, market_id: str = typer.Argument(..., help="Target market identifier")):
    """Run research on a market and present results."""

    settings: Settings = ctx.obj["settings"]
    markets = _load_markets(settings)
    selected = next((m for m in markets if m.id == market_id), None)
    if not selected:
        typer.echo(f"Market {market_id} not found in filtered list.")
        raise typer.Exit(code=1)

    orchestrator = ResearchOrchestrator(settings)
    result = orchestrator.run_research(selected.id, selected.question)
    edge_report = evaluate_market(result.probability_yes, selected.prices, selected.resolves_at)
    display_review(console, markets, selected, edge_report, result.rationale, result.citations, result.confidence)

    engine = ctx.obj["engine"]
    settings: Settings = ctx.obj["settings"]
    markets = {market.id: market for market in _load_markets(settings)}
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

        proposal = Proposal(
            market_id=selected.id,
            side=edge_report.side,
            stake=recommend_stake(
                settings.sizing.policy,
                settings.sizing.bankroll,
                settings.sizing.risk_budget,
                result.confidence,
                edge_report.roi,
                settings.sizing.max_fraction,
            ),
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
            proposal.stake = stake
        proposal.accepted = True
        session.add(proposal)

        market = markets.get(proposal.market_id)
        entry_price = 1.0
        if market:
            entry_price = market.prices.get(proposal.side, 1.0)

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
        if not existing_position:
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
        rows = session.exec(select(Position)).all()
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
    for row in rows:
        table.add_row(
            row.market_id,
            row.side,
            f"${row.stake:,.2f}",
            f"{row.entry_price:.2f}",
            f"{row.mark_price:.2f}",
            f"${row.unrealized_pnl:,.2f}",
        )
    console.print(table)


@app.command()
def history(ctx: typer.Context, csv: Optional[Path] = typer.Option(None, help="Export path")):
    """Show trade history or export to CSV."""

    engine = ctx.obj["engine"]
    with session_scope(engine) as session:
        trades = session.exec(select(Trade)).all()

    if not trades:
        typer.echo("No trades recorded yet.")
        return

    if csv:
        lines = ["id,market_id,side,stake,entry_price,timestamp"]
        for trade in trades:
            lines.append(
                f"{trade.id},{trade.market_id},{trade.side},{trade.stake},{trade.entry_price},{trade.timestamp.isoformat()}"
            )
        csv.write_text("\n".join(lines), encoding="utf-8")
        typer.echo(f"Exported {len(trades)} trades to {csv}")
    else:
        table = Table(show_header=True, header_style="bold")
        table.add_column("ID")
        table.add_column("Market")
        table.add_column("Side")
        table.add_column("Stake")
        table.add_column("Entry")
        table.add_column("Timestamp")
        for trade in trades:
            table.add_row(
                str(trade.id),
                trade.market_id,
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
        "liquidity": settings.liquidity.__dict__,
        "research": settings.research.__dict__,
        "sizing": settings.sizing.__dict__,
        "updates": settings.updates.__dict__,
        "xai_api_key": "set" if settings.xai_api_key else "missing",
        "config_path": str(CONFIG_PATH),
    }
    console.print_json(data=payload)


def run():
    app()


__all__ = ["app", "run"]
