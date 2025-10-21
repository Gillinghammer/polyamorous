"""Portfolio command handler for Polly CLI."""

from rich.console import Console

from polly.config import PaperTradingConfig
from polly.storage.trades import TradeRepository
from polly.ui.formatters import (
    create_portfolio_panel,
    create_active_positions_table,
    create_recent_trades_table,
)

console = Console()


def handle_portfolio(trade_repo: TradeRepository, paper_config: PaperTradingConfig) -> None:
    """Handle /portfolio command.
    
    Args:
        trade_repo: Trade repository instance
        paper_config: Paper trading configuration
    """
    try:
        # Get portfolio metrics
        metrics = trade_repo.metrics(starting_cash=paper_config.starting_cash)
        
        # Display metrics panel
        panel = create_portfolio_panel(metrics)
        console.print(panel)
        
        # Display active positions
        active_trades = trade_repo.list_active()
        if active_trades:
            console.print()
            table = create_active_positions_table(active_trades)
            console.print(table)
        else:
            console.print("\n[dim]No active positions[/dim]")
        
        # Display recent trades
        recent_trades = [t for t in metrics.recent_trades if t.status in ("won", "lost", "closed")]
        if recent_trades:
            console.print()
            table = create_recent_trades_table(recent_trades)
            console.print(table)
        else:
            console.print("\n[dim]No completed trades yet[/dim]")
        
        # Display cash balances
        console.print(f"\n[bold]Cash Available:[/bold] ${metrics.cash_available:,.2f}")
        console.print(f"[bold]Cash In Play:[/bold] ${metrics.cash_in_play:,.2f}")
        
    except Exception as e:
        console.print(f"[red]Error loading portfolio: {e}[/red]")

