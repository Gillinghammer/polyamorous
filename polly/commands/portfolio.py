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
    create_grouped_position_display,
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
        
        # Get real balance if in real mode
        real_balance = None
        if trading_config.mode == "real" and trading_service:
            try:
                balances = trading_service.get_balances()
                if "error" not in balances:
                    real_balance = balances.get("usdc", 0.0)
            except Exception:
                pass
        
        # Get portfolio metrics filtered by current mode
        metrics = trade_repo.metrics(
            starting_cash=trading_config.starting_cash,
            filter_mode=trading_config.mode,
            real_balance=real_balance
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
            
            # Separate grouped and ungrouped positions
            grouped_trades = {}
            ungrouped_trades = []
            
            for trade in active_trades:
                if trade.is_grouped and trade.event_id:
                    if trade.event_id not in grouped_trades:
                        grouped_trades[trade.event_id] = []
                    grouped_trades[trade.event_id].append(trade)
                else:
                    ungrouped_trades.append(trade)
            
            # Display grouped positions first
            if grouped_trades:
                console.print("[bold cyan]Grouped Event Positions:[/bold cyan]\n")
                for event_id, trades in grouped_trades.items():
                    event_title = trades[0].event_title or "Unknown Event"
                    panel = create_grouped_position_display(event_id, event_title, trades)
                    console.print(panel)
                    console.print()
            
            # Display ungrouped positions
            if ungrouped_trades:
                if grouped_trades:
                    console.print("[bold cyan]Individual Positions:[/bold cyan]\n")
                table = create_active_positions_table(ungrouped_trades, live_positions)
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

