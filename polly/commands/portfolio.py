"""Portfolio command handler for Polly CLI."""

from typing import Optional

from rich.console import Console

from polly.config import TradingConfig
from polly.services.trading import TradingService
from polly.storage.trades import TradeRepository
from polly.ui.formatters import (
    create_portfolio_panel,
    create_active_positions_table,
    create_recent_trades_table,
)

console = Console()


def handle_portfolio(
    trade_repo: TradeRepository,
    trading_config: TradingConfig,
    trading_service: Optional[TradingService] = None,
) -> None:
    """Handle /portfolio command.
    
    Args:
        trade_repo: Trade repository instance
        trading_config: Trading configuration
        trading_service: Trading service (for real mode balance display)
    """
    try:
        # Display trading mode indicator
        mode_badge = "[green]PAPER MODE[/green]" if trading_config.mode == "paper" else "[red]REAL MODE[/red]"
        console.print(f"\n{mode_badge}")
        console.print(f"[dim]Showing {trading_config.mode} trades only[/dim]\n")
        
        # Get portfolio metrics filtered by current mode
        metrics = trade_repo.metrics(
            starting_cash=trading_config.starting_cash,
            filter_mode=trading_config.mode
        )
        
        # Display metrics panel
        panel = create_portfolio_panel(metrics)
        console.print(panel)
        
        # If real mode and trading service available, show actual balances
        if trading_config.mode == "real":
            if trading_service:
                console.print("\n[bold cyan]On-Chain Balances:[/bold cyan]")
                try:
                    balances = trading_service.get_balances()
                    if "error" in balances:
                        console.print(f"  [yellow]Error: {balances['error']}[/yellow]")
                    else:
                        # Display all balance info
                        usdc_balance = balances.get("usdc", 0.0)
                        console.print(f"  USDC: ${usdc_balance:,.2f}")
                        
                        # Show raw balance data for debugging if needed
                        if usdc_balance == 0:
                            console.print(f"  [dim](Raw data: {balances})[/dim]")
                except Exception as e:
                    console.print(f"  [yellow]Could not fetch: {e}[/yellow]")
                    import traceback
                    console.print(f"  [dim]{traceback.format_exc()}[/dim]")
            else:
                console.print("\n[yellow]⚠️  POLYGON_PRIVATE_KEY not set - cannot fetch on-chain balances[/yellow]")
                console.print("[dim]Add POLYGON_PRIVATE_KEY to .env to enable balance checking[/dim]")
        
        # Display active positions (filtered by current mode)
        active_trades = trade_repo.list_active(filter_mode=trading_config.mode)
        
        # For real mode, enrich with live Polymarket data
        live_positions = []
        if trading_config.mode == "real" and trading_service:
            try:
                live_positions = trading_service.get_live_positions()
            except Exception as e:
                console.print(f"[dim]Could not fetch live positions: {e}[/dim]")
        
        if active_trades:
            console.print()
            table = create_active_positions_table(active_trades, live_positions)
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
        
        # Display cash balances (paper tracking)
        console.print(f"\n[bold]Tracked Cash Available:[/bold] ${metrics.cash_available:,.2f}")
        console.print(f"[bold]Cash In Play:[/bold] ${metrics.cash_in_play:,.2f}")
        
    except Exception as e:
        console.print(f"[red]Error loading portfolio: {e}[/red]")

