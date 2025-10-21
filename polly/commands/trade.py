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
        # Record trade in database
        trade = Trade(
            id=None,
            market_id=market.id,
            question=market.question,
            category=market.category,
            selected_option=matching_outcome.outcome,
            entry_odds=result.executed_price,
            stake_amount=amount,
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
        console.print(f"[dim]Executed Price: ${result.executed_price:.3f}[/dim]")
        console.print(f"[dim]Shares: {result.executed_size:.2f}[/dim]")
    else:
        console.print(f"[red]✗ Trade failed: {result.error}[/red]")


def handle_close(
    args: str,
    trade_repo: TradeRepository,
    trading_service: Optional[TradingService],
    trading_config: TradingConfig,
) -> None:
    """Handle /close <trade_id> command.

    Args:
        args: Command arguments (trade ID)
        trade_repo: Trade repository
        trading_service: Trading service instance
        trading_config: Trading configuration
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
        return

    try:
        trade_id = int(args.strip())
    except ValueError:
        console.print("[red]Invalid trade ID. Must be a number.[/red]")
        return

    # Get all active trades to find the one to close
    active_trades = trade_repo.list_active()
    trade_to_close = None

    for trade in active_trades:
        if trade.id == trade_id:
            trade_to_close = trade
            break

    if not trade_to_close:
        console.print(f"[red]Active trade with ID {trade_id} not found[/red]")
        return

    # Only allow closing real trades via this command
    if trade_to_close.trade_mode != "real":
        console.print("[yellow]This is a paper trade. It will resolve automatically at market expiry.[/yellow]")
        return

    # Display trade summary
    console.print()
    console.print(Panel(f"[bold yellow]Close Position[/bold yellow]", style="yellow"))
    console.print()
    console.print(f"[bold]Trade ID:[/bold] {trade_to_close.id}")
    console.print(f"[bold]Market:[/bold] {trade_to_close.question}")
    console.print(f"[bold]Position:[/bold] {trade_to_close.selected_option}")
    console.print(f"[bold]Entry Price:[/bold] ${trade_to_close.entry_odds:.3f}")
    console.print(f"[bold]Stake:[/bold] ${trade_to_close.stake_amount:.2f}")
    console.print()

    # We need to determine the token_id and shares to sell
    # For now, we need to fetch current market data or store token_id with trade
    # This is a limitation - we'll need the token_id
    console.print("[yellow]Note: Position closing requires market lookup[/yellow]")
    console.print("[dim]Feature requires storing token_id with trade - will be added in future update[/dim]")
    
    # TODO: Full implementation requires:
    # 1. Store token_id in Trade model
    # 2. Calculate shares from stake_amount and entry_odds
    # 3. Execute sell order
    # 4. Update trade record with exit details
    
    console.print("[yellow]Manual position closing will be fully implemented in next update[/yellow]")

