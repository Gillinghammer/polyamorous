"""Trade execution command handlers for Polly CLI."""

from datetime import datetime, timezone
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from polly.config import TradingConfig
from polly.models import Market, Trade
from polly.services.trading import TradingService
from polly.services.validators import (
    check_usdc_balance,
    validate_market_active,
    validate_token_id,
    validate_trade_size,
)
from polly.storage.trades import TradeRepository
from polly.ui.formatters import format_profit

console = Console()


def get_available_balance(
    trading_config: TradingConfig,
    trade_repo: TradeRepository,
    trading_service: Optional[TradingService],
) -> float:
    """Get available balance for trading (real or paper).
    
    Args:
        trading_config: Trading configuration
        trade_repo: Trade repository
        trading_service: Trading service (for real mode)
    
    Returns:
        Available balance in USDC
    """
    if trading_config.mode == "real" and trading_service:
        # Real mode: get actual wallet balance
        balances = trading_service.get_balances()
        return balances.get("usdc", 0.0)
    else:
        # Paper mode: calculate from starting cash + realized - active
        metrics = trade_repo.metrics(starting_cash=trading_config.starting_cash, filter_mode="paper")
        return metrics.cash_available


def prompt_for_amount(
    available_balance: float,
    default_stake: float,
    market_question: str,
    outcome_name: str,
    outcome_price: float,
    is_real_mode: bool,
) -> Optional[float]:
    """Prompt user for stake amount with balance and payout display.
    
    Args:
        available_balance: Available balance to display
        default_stake: Default stake amount
        market_question: Market question for display
        outcome_name: Outcome name for display
        outcome_price: Current price for payout calculation
        is_real_mode: Whether in real trading mode
    
    Returns:
        Stake amount or None if cancelled
    """
    mode_label = "[red]REAL[/red]" if is_real_mode else "[green]PAPER[/green]"
    
    console.print()
    console.print(Panel(f"[bold]{mode_label} Position Entry[/bold]", border_style="cyan"))
    console.print()
    console.print(f"[bold]Market:[/bold] {market_question}")
    console.print(f"[bold]Outcome:[/bold] {outcome_name}")
    console.print(f"[bold]Current Price:[/bold] ${outcome_price:.3f}")
    console.print(f"[bold]Available Balance:[/bold] ${available_balance:.2f}")
    console.print()
    
    while True:
        amount_str = Prompt.ask(
            f"Enter stake amount (default: ${default_stake:.0f}, max: ${available_balance:.2f})",
            default=str(default_stake),
        )
        
        try:
            amount = float(amount_str)
            if amount <= 0:
                console.print("[red]Amount must be greater than 0[/red]")
                continue
            if amount > available_balance:
                console.print(f"[red]Amount exceeds available balance of ${available_balance:.2f}[/red]")
                continue
            
            # Show projected payout
            estimated_shares = amount / outcome_price if outcome_price > 0 else 0
            max_payout = estimated_shares * 1.0  # Max payout is shares * $1
            profit = max_payout - amount
            
            console.print()
            console.print(f"[bold]Stake Amount:[/bold] ${amount:.2f}")
            console.print(f"[bold]Est. Shares:[/bold] {estimated_shares:.2f}")
            console.print(f"[bold]Max Payout:[/bold] ${max_payout:.2f}")
            console.print(f"[bold]Potential Profit:[/bold] ${profit:.2f} ({(profit/amount)*100:.1f}%)")
            console.print()
            
            return amount
            
        except ValueError:
            console.print("[red]Invalid amount. Please enter a number.[/red]")
            continue


def handle_trade(
    args: str,
    markets_cache: List[Market],
    trading_service: Optional[TradingService],
    trade_repo: TradeRepository,
    trading_config: TradingConfig,
) -> None:
    """Handle /trade <market_number> <outcome> command.

    Args:
        args: Command arguments
        markets_cache: Cached markets from /polls
        trading_service: Trading service instance
        trade_repo: Trade repository
        trading_config: Trading configuration
    """
    # Check if in real trading mode
    if trading_config.mode != "real":
        console.print("[yellow]Paper trading mode - use /research flow for paper trades[/yellow]")
        console.print("[dim]To enable real trading, set mode: real in config[/dim]")
        return

    # Check if trading service is available
    if not trading_service:
        console.print("[red]Trading service not initialized. Check POLYGON_PRIVATE_KEY.[/red]")
        return

    # Parse arguments
    parts = args.split()
    if len(parts) < 2:
        console.print("[red]Usage: /trade <market_number> <outcome>[/red]")
        console.print("[dim]Example: /trade 5 Yes[/dim]")
        return

    try:
        market_num = int(parts[0])
        outcome_name = parts[1]
    except ValueError:
        console.print("[red]Invalid arguments. Market number must be a number.[/red]")
        return

    # Validate market number
    if not markets_cache:
        console.print("[yellow]No markets cached. Run /polls first.[/yellow]")
        return

    if market_num < 1 or market_num > len(markets_cache):
        console.print(f"[red]Invalid market number. Must be 1-{len(markets_cache)}[/red]")
        return

    market = markets_cache[market_num - 1]

    # Validate market is active
    is_active, error_msg = validate_market_active(market)
    if not is_active:
        console.print(f"[red]{error_msg}[/red]")
        return

    # Find matching outcome
    matching_outcome = None
    for outcome in market.outcomes:
        if outcome.outcome.lower() == outcome_name.lower():
            matching_outcome = outcome
            break

    if not matching_outcome:
        console.print(f"[red]Outcome '{outcome_name}' not found in market[/red]")
        valid_outcomes = ", ".join([f"{o.outcome} (${o.price:.3f})" for o in market.outcomes])
        console.print(f"[dim]Valid outcomes: {valid_outcomes}[/dim]")
        return
    
    # Debug: show token ID being used
    console.print(f"[dim]Using token_id: {matching_outcome.token_id}[/dim]")

    # Validate token ID
    if not validate_token_id(matching_outcome.token_id, market):
        console.print("[red]Invalid token ID for market[/red]")
        return

    # Get available balance
    available_balance = get_available_balance(trading_config, trade_repo, trading_service)

    # Prompt for amount with balance and payout display
    amount = prompt_for_amount(
        available_balance=available_balance,
        default_stake=trading_config.default_stake,
        market_question=market.question,
        outcome_name=matching_outcome.outcome,
        outcome_price=matching_outcome.price,
        is_real_mode=True,
    )
    
    if amount is None:
        console.print("[yellow]Trade cancelled[/yellow]")
        return

    # Final confirmation for real money
    console.print(Panel(f"[bold red]⚠️  REAL MONEY TRADE[/bold red]", style="red"))
    if not Confirm.ask("Execute real trade?", default=False):
        console.print("[yellow]Trade cancelled[/yellow]")
        return

    # Execute trade - pass the stake amount, let trading service calculate shares from orderbook
    console.print("\n[dim]Executing trade...[/dim]")
    result = trading_service.execute_market_buy_with_amount(
        token_id=matching_outcome.token_id,
        stake_amount=amount
    )

    if result.success:
        # Calculate actual cost
        actual_cost = result.executed_price * result.executed_size
        
        # Warn if execution price differs significantly from expected
        if abs(actual_cost - amount) > 0.50:  # More than 50¢ difference
            console.print(f"\n[bold yellow]⚠️  PRICE WARNING[/bold yellow]")
            console.print(f"[yellow]Expected to spend: ${amount:.2f}[/yellow]")
            console.print(f"[yellow]Actually spent: ${actual_cost:.2f}[/yellow]")
            console.print(f"[yellow]Difference: ${abs(actual_cost - amount):.2f}[/yellow]")
            console.print(f"[dim]Market price may have moved during order execution[/dim]\n")
        
        # Record trade in database with ACTUAL execution values
        trade = Trade(
            id=None,
            market_id=market.id,
            question=market.question,
            category=market.category,
            selected_option=matching_outcome.outcome,
            entry_odds=result.executed_price,
            stake_amount=actual_cost,  # Use actual amount spent
            entry_timestamp=datetime.now(tz=timezone.utc),
            predicted_probability=0.0,  # Manual trade, no prediction
            confidence=0.0,  # Manual trade, no confidence
            research_id=None,
            status="active",
            resolves_at=market.end_date,
            actual_outcome=None,
            profit_loss=None,
            closed_at=None,
            trade_mode="real",
            order_id=result.order_id,
        )
        trade_repo.record_trade(trade)

        console.print("[green]✓ Trade executed successfully[/green]")
        console.print(f"[dim]Order ID: {result.order_id}[/dim]")
        console.print(f"[dim]Executed Price: ${result.executed_price:.3f} per share[/dim]")
        console.print(f"[dim]Shares: {result.executed_size:.2f}[/dim]")
        console.print(f"[dim]Total Cost: ${actual_cost:.2f}[/dim]")
    else:
        console.print(f"[red]✗ Trade failed: {result.error}[/red]")


def handle_close(
    args: str,
    trade_repo: TradeRepository,
    trading_service: Optional[TradingService],
    trading_config: TradingConfig,
    markets_cache: List[Market] = None,
) -> None:
    """Handle /close <trade_id> command.

    Args:
        args: Command arguments (trade ID)
        trade_repo: Trade repository
        trading_service: Trading service instance
        trading_config: Trading configuration
        markets_cache: Optional cached markets for token lookup
    """
    # Check if in real trading mode
    if trading_config.mode != "real":
        console.print("[yellow]Position closing only available in real trading mode[/yellow]")
        return

    # Check if trading service is available
    if not trading_service:
        console.print("[red]Trading service not initialized. Check POLYGON_PRIVATE_KEY.[/red]")
        return

    # Parse trade ID
    if not args.strip():
        console.print("[red]Usage: /close <trade_id>[/red]")
        console.print("[dim]Example: /close 5[/dim]")
        console.print("[dim]Use /portfolio to see active position IDs[/dim]")
        return

    try:
        trade_id = int(args.strip())
    except ValueError:
        console.print("[red]Invalid trade ID. Must be a number.[/red]")
        return

    # Get all active trades to find the one to close
    active_trades = trade_repo.list_active(filter_mode="real")
    trade_to_close = None

    for trade in active_trades:
        if trade.id == trade_id:
            trade_to_close = trade
            break

    if not trade_to_close:
        console.print(f"[red]Active real trade with ID {trade_id} not found[/red]")
        console.print("[dim]Use /portfolio to see active positions[/dim]")
        return

    # Get live position data to find token_id and shares
    live_positions = trading_service.get_live_positions()
    
    matching_position = None
    for pos in live_positions:
        if pos.get('conditionId') == trade_to_close.market_id and pos.get('outcome') == trade_to_close.selected_option:
            matching_position = pos
            break
    
    if not matching_position:
        console.print("[red]Could not find live position data for this trade[/red]")
        console.print("[dim]The position may have been manually closed or resolved already[/dim]")
        return
    
    # Extract position details
    token_id = matching_position.get('asset')
    current_size = float(matching_position.get('size', 0))
    current_price = float(matching_position.get('curPrice', 0))
    current_value = float(matching_position.get('currentValue', 0))
    unrealized_pnl = float(matching_position.get('cashPnl', 0))
    
    # Display position summary with current market data
    console.print()
    console.print(Panel(f"[bold yellow]Close Position[/bold yellow]", style="yellow"))
    console.print()
    console.print(f"[bold]Trade ID:[/bold] {trade_to_close.id}")
    console.print(f"[bold]Market:[/bold] {trade_to_close.question}")
    console.print(f"[bold]Position:[/bold] {trade_to_close.selected_option}")
    console.print(f"[bold]Shares:[/bold] {current_size:.2f}")
    console.print(f"[bold]Entry Price:[/bold] ${trade_to_close.entry_odds:.3f}")
    console.print(f"[bold]Current Price:[/bold] ${current_price:.3f}")
    console.print(f"[bold]Cost Basis:[/bold] ${trade_to_close.stake_amount:.2f}")
    console.print(f"[bold]Current Value:[/bold] ${current_value:.2f}")
    
    pnl_color = "green" if unrealized_pnl >= 0 else "red"
    pnl_sign = "+" if unrealized_pnl >= 0 else ""
    console.print(f"[bold]Unrealized P&L:[/bold] [{pnl_color}]{pnl_sign}${unrealized_pnl:.2f}[/{pnl_color}]")
    console.print()

    # Confirm closure
    if not Confirm.ask("Close this position at current market price?", default=False):
        console.print("[yellow]Position close cancelled[/yellow]")
        return

    # Execute sell order
    console.print("\n[dim]Executing market sell...[/dim]")
    result = trading_service.execute_market_sell(token_id, current_size)

    if result.success:
        # Update trade in database
        from datetime import datetime, timezone
        final_pnl = current_value - trade_to_close.stake_amount
        
        trade_repo.update_trade_outcome(
            trade_id=trade_to_close.id,
            actual_outcome=trade_to_close.selected_option,  # Manually closed
            profit_loss=final_pnl
        )

        console.print("[green]✓ Position closed successfully[/green]")
        console.print(f"[dim]Order ID: {result.order_id}[/dim]")
        console.print(f"[dim]Exit Price: ${result.executed_price:.3f}[/dim]")
        console.print(f"[dim]Final P&L: {format_profit(final_pnl)}[/dim]")
    else:
        console.print(f"[red]✗ Position close failed: {result.error}[/red]")

