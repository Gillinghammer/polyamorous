"""Rich formatting utilities for Polly CLI."""

from datetime import timedelta
from typing import Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from polly.models import Market, MarketGroup, PortfolioMetrics, Trade

console = Console()


def format_odds(odds_dict: Dict[str, float]) -> str:
    """Format odds dictionary as readable string.
    
    Example: {"Yes": 0.58, "No": 0.42} -> "Yes 58%"
    """
    if not odds_dict:
        return "N/A"
    
    # Find the option with the highest odds
    best_option = max(odds_dict.items(), key=lambda x: x[1])
    return f"{best_option[0]} {best_option[1]:.0%}"


def format_time_remaining(td: timedelta) -> str:
    """Format timedelta as human-readable string.
    
    Examples: "7d 14h", "2h 30m", "45m"
    """
    total_seconds = int(td.total_seconds())
    if total_seconds <= 0:
        return "Expired"
    
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    
    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def format_profit(value: float) -> str:
    """Format profit/loss with color.
    
    Returns: Green for positive, red for negative, white for zero.
    """
    if value > 0:
        return f"[green]+${value:.2f}[/green]"
    elif value < 0:
        return f"[red]-${abs(value):.2f}[/red]"
    else:
        return f"${value:.2f}"


def format_payout(stake: float, odds: float) -> str:
    """Format potential payout from stake and odds.
    
    Example: stake=$100, odds=0.58 -> "$158.00 (+58%)"
    """
    payout = stake / odds if odds > 0 else 0
    gain = payout - stake
    gain_pct = (gain / stake * 100) if stake > 0 else 0
    return f"${payout:.2f} (+{gain_pct:.0f}%)"


def create_polls_table(items: List[Market | MarketGroup]) -> Table:
    """Create Rich table for displaying polls (both binary markets and grouped events)."""
    table = Table(title="Available Polls", show_header=True, header_style="bold cyan")
    
    table.add_column("ID", style="dim", width=3)
    table.add_column("Category", style="cyan", width=12)
    table.add_column("Question", style="white", width=55)
    table.add_column("Odds", style="yellow", width=12, justify="right")
    table.add_column("Expires", style="magenta", width=8)
    table.add_column("Liquidity", style="green", justify="right", width=10)
    
    for i, item in enumerate(items, 1):
        if isinstance(item, MarketGroup):
            # Display grouped multi-outcome event
            time_str = format_time_remaining(item.time_remaining)
            
            # Show liquidity with k/M suffix
            if item.liquidity >= 1_000_000:
                liquidity_str = f"${item.liquidity/1_000_000:.1f}M"
            elif item.liquidity >= 1_000:
                liquidity_str = f"${item.liquidity/1_000:.0f}k"
            else:
                liquidity_str = f"${item.liquidity:.0f}"
            
            # Truncate category
            category = item.category or "Other"
            if len(category) > 11:
                category = category[:9] + ".."
            
            # Truncate title
            title = item.title
            if len(title) > 52:
                title = title[:49] + "..."
            
            # Get top 2 markets for preview
            top_markets = item.get_top_markets(2)
            if top_markets:
                top_preview = ", ".join([
                    f"{m.question.split('Will ')[-1].split(' win')[0] if 'Will ' in m.question else m.question[:15]}"
                    f" {next((o.price for o in m.outcomes if o.outcome.lower() in ('yes', 'y')), 0.0):.0%}"
                    for m in top_markets
                ])
                if len(top_preview) > 50:
                    top_preview = top_preview[:47] + "..."
            else:
                top_preview = ""
            
            # Show number of markets as "odds"
            odds_str = f"{len(item.markets)} opts"
            
            table.add_row(
                str(i),
                category,
                f"⬐ {title}\n[dim]  {top_preview}[/dim]" if top_preview else f"⬐ {title}",
                odds_str,
                time_str,
                liquidity_str,
                style="bold" if item.liquidity > 1_000_000 else None
            )
        else:
            # Display individual binary market
            odds_str = format_odds(item.formatted_odds())
            time_str = format_time_remaining(item.time_remaining)
            
            # Show liquidity with k/M suffix
            if item.liquidity >= 1_000_000:
                liquidity_str = f"${item.liquidity/1_000_000:.1f}M"
            elif item.liquidity >= 1_000:
                liquidity_str = f"${item.liquidity/1_000:.0f}k"
            else:
                liquidity_str = f"${item.liquidity:.0f}"
            
            # Truncate category
            category = item.category or "Other"
            if len(category) > 11:
                category = category[:9] + ".."
            
            # Truncate question
            question = item.question
            if len(question) > 52:
                question = question[:49] + "..."
            
            table.add_row(
                str(i),
                category,
                question,
                odds_str,
                time_str,
                liquidity_str
            )
    
    return table


def create_portfolio_panel(metrics: PortfolioMetrics) -> Panel:
    """Create Rich panel for portfolio metrics."""
    wins = int(metrics.win_rate * len(metrics.recent_trades)) if metrics.recent_trades else 0
    total_resolved = len(metrics.recent_trades)
    
    win_rate_str = f"{wins}/{total_resolved} ({metrics.win_rate:.0%})" if total_resolved > 0 else "N/A"
    profit_str = format_profit(metrics.total_profit)
    avg_profit_str = format_profit(metrics.average_profit)
    apr_str = f"{metrics.projected_apr:.1%}" if metrics.projected_apr > 0 else "N/A"
    
    content = f"""
[bold]Active Positions:[/bold] {metrics.active_positions}
[bold]Win Rate:[/bold] {win_rate_str}
[bold]Total Profit:[/bold] {profit_str}
[bold]Average Profit:[/bold] {avg_profit_str}
[bold]Projected APR:[/bold] {apr_str}
    """.strip()
    
    return Panel(content, title="Portfolio Metrics", border_style="blue")


def create_active_positions_table(trades: List[Trade], live_positions: List[dict] = None) -> Table:
    """Create Rich table for active positions with live data if available.
    
    Args:
        trades: List of Trade objects from database
        live_positions: Optional list of live position data from Polymarket API
    """
    # Map live positions by condition_id for quick lookup
    live_by_market = {}
    if live_positions:
        for pos in live_positions:
            market_id = pos.get('conditionId')
            if market_id:
                live_by_market[market_id] = pos
    
    # Add extra columns if we have live data
    has_live_data = bool(live_by_market)
    
    table = Table(title="Active Positions", show_header=True, header_style="bold cyan")
    
    table.add_column("ID", style="dim", width=3)
    table.add_column("Question", style="white", width=35)
    table.add_column("Bet", style="yellow", width=12)
    table.add_column("Entry", style="magenta", width=8)
    
    if has_live_data:
        table.add_column("Current", style="cyan", width=8)
        table.add_column("Value", style="green", width=10)
        table.add_column("P&L", style="white", width=12)
    else:
        table.add_column("Days Left", style="green", width=10)
    
    for trade in trades:
        question = trade.question
        if len(question) > 32:
            question = question[:29] + "..."
        
        from datetime import datetime, timezone
        days_left = (trade.resolves_at - datetime.now(tz=timezone.utc)).days
        
        # Get live position data if available
        live_data = live_by_market.get(trade.market_id)
        
        if has_live_data and live_data:
            current_price = float(live_data.get('curPrice', 0))
            current_value = float(live_data.get('currentValue', 0))
            cash_pnl = float(live_data.get('cashPnl', 0))
            
            pnl_str = format_profit(cash_pnl)
            
            table.add_row(
                str(trade.id),
                question,
                trade.selected_option,
                f"{trade.entry_odds:.0%}",
                f"{current_price:.0%}",
                f"${current_value:.2f}",
                pnl_str
            )
        else:
            table.add_row(
                str(trade.id),
                question,
                trade.selected_option,
                f"{trade.entry_odds:.0%}",
                f"{days_left}d"
            )
    
    return table


def create_recent_trades_table(trades: List[Trade]) -> Table:
    """Create Rich table for recent resolved trades."""
    table = Table(title="Recent Trades", show_header=True, header_style="bold cyan")
    
    table.add_column("Question", style="white", width=40)
    table.add_column("Outcome", style="yellow", width=10)
    table.add_column("P&L", style="white", width=12)
    table.add_column("Duration", style="magenta", width=10)
    
    for trade in trades[:10]:  # Only show last 10
        if trade.status not in ("won", "lost", "closed"):
            continue
            
        question = trade.question
        if len(question) > 37:
            question = question[:34] + "..."
        
        pnl_str = format_profit(trade.profit_loss or 0.0)
        
        if trade.closed_at and trade.entry_timestamp:
            duration_days = (trade.closed_at - trade.entry_timestamp).days
            duration_str = f"{duration_days}d"
        else:
            duration_str = "N/A"
        
        table.add_row(
            question,
            trade.status.upper(),
            pnl_str,
            duration_str
        )
    
    return table


def create_grouped_position_display(
    event_id: str,
    event_title: str,
    trades: List[Trade],
) -> Panel:
    """Create display for grouped positions within same event.
    
    Args:
        event_id: Event ID
        event_title: Event title
        trades: List of trades in this event group
        
    Returns:
        Rich Panel with grouped position display
    """
    if not trades:
        return Panel("No positions", title="Grouped Positions")
    
    # Calculate combined metrics
    total_stake = sum(t.stake_amount for t in trades)
    active_count = sum(1 for t in trades if t.status == "active")
    
    # Build content
    content = f"[bold cyan]{event_title}[/bold cyan]\n"
    content += f"[dim]Event ID: {event_id}[/dim]\n\n"
    
    if trades[0].group_strategy:
        content += f"[bold]Strategy:[/bold] {trades[0].group_strategy}\n"
    
    content += f"[bold]Total Stake:[/bold] ${total_stake:.2f}\n"
    content += f"[bold]Active Positions:[/bold] {active_count}/{len(trades)}\n\n"
    
    content += "[bold]Positions:[/bold]\n"
    for i, trade in enumerate(trades, 1):
        # Extract candidate name from question
        candidate = trade.question.split("Will ")[-1].split(" win")[0] if "Will " in trade.question else trade.question[:30]
        
        status_icon = "●" if trade.status == "active" else ("✓" if trade.status == "won" else "✗")
        status_color = "yellow" if trade.status == "active" else ("green" if trade.status == "won" else "red")
        
        content += f"  [{status_color}]{status_icon}[/{status_color}] {candidate} {trade.selected_option} @ {trade.entry_odds:.0%}"
        
        if trade.profit_loss is not None:
            pnl_str = format_profit(trade.profit_loss)
            content += f" | {pnl_str}"
        else:
            content += f" | ${trade.stake_amount:.0f}"
        
        content += "\n"
    
    # Calculate combined P&L if any resolved
    resolved_trades = [t for t in trades if t.profit_loss is not None]
    if resolved_trades:
        combined_pnl = sum(t.profit_loss for t in resolved_trades)
        content += f"\n[bold]Combined P&L:[/bold] {format_profit(combined_pnl)}"
    
    return Panel(content, title="📊 Grouped Event Positions", border_style="cyan")

