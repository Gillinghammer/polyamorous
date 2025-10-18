from __future__ import annotations
import csv
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlmodel import select

from .config import CONFIG_PATH, Settings, load_settings
from .logging import configure_logging
from .models.db import Market, Position, Proposal, Research, Trade
from .services.persistence import get_engine, init_db, session_scope
from .services.workflows import accept_latest_proposal, load_filtered_markets, run_research_flow
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
@app.command()
def scan(ctx: typer.Context):
    """Scan and display candidate Polymarket markets."""

    settings: Settings = ctx.obj["settings"]
    markets = load_filtered_markets(settings, ctx.obj["engine"])
    if not markets:
        typer.echo("No markets met the configured filters.")
        return
    display_scan(console, markets)


@app.command()
def review(ctx: typer.Context, market_id: str = typer.Argument(..., help="Target market identifier")):
    """Run research on a market and present results."""

    settings: Settings = ctx.obj["settings"]
    engine = ctx.obj["engine"]
    markets = load_filtered_markets(settings, engine)
    if not markets:
        typer.echo("No markets met the configured filters. Run `pm scan` first.")
        raise typer.Exit(code=1)
    selected = next((m for m in markets if m.id == market_id), None)
    if not selected:
        typer.echo(f"Market {market_id} not found in filtered list.")
        raise typer.Exit(code=1)

    outcome = run_research_flow(engine, settings, selected)
    display_review(
        console,
        markets,
        selected,
        outcome.edge_report,
        outcome.result.rationale,
        outcome.result.citations,
        outcome.result.confidence,
    )

    if outcome.disqualifications:
        console.print(
            Panel(
                "\n".join(outcome.disqualifications),
                title="No proposal generated",
                border_style="red",
            )
        )
        typer.echo(f"Stored research #{outcome.research.id} without proposal.")
        return

    typer.echo(
        f"Stored research #{outcome.research.id} and proposal #{outcome.proposal.id} for {selected.slug}."
    )


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
    try:
        outcome = accept_latest_proposal(engine, settings, market_id, stake, side)
    except ValueError as exc:  # pragma: no cover - CLI guard rails
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Accepted proposal #{outcome.proposal.id}; recorded trade #{outcome.trade.id}.")


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
