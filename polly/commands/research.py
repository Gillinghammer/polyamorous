"""Research command handler for Polly CLI."""

import asyncio
from datetime import datetime, timezone
from typing import List

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm

from polly.commands.trade import get_available_balance, prompt_for_amount
from polly.config import TradingConfig, ResearchConfig
from polly.models import Market, ResearchProgress, Trade
from polly.services.evaluator import PositionEvaluator
from polly.services.polymarket import PolymarketService
from polly.services.research import ResearchService
from polly.services.trading import TradingService
from polly.services.validators import check_usdc_balance, validate_market_active
from polly.storage.research import ResearchRepository
from polly.storage.trades import TradeRepository
from polly.ui.formatters import format_payout

console = Console()


def handle_research(
    args: str,
    markets_cache: List[Market],
    polymarket: PolymarketService,
    research_service: ResearchService,
    evaluator: PositionEvaluator,
    research_repo: ResearchRepository,
    trade_repo: TradeRepository,
    research_config: ResearchConfig,
    trading_config: TradingConfig,
    trading_service: TradingService | None = None,
) -> None:
    """Handle /research <poll_id> command.
    
    Args:
        args: Poll ID (1-based index from polls list)
        markets_cache: Cached markets from last /polls command
        polymarket: Polymarket service instance
        research_service: Research service instance
        evaluator: Position evaluator instance
        research_repo: Research repository instance
        trade_repo: Trade repository instance
        research_config: Research configuration
        trading_config: Trading configuration
        trading_service: Trading service (required for real trading)
    """
    # Parse poll ID
    if not args.strip():
        console.print("[red]Error: Poll ID required. Usage: /research <poll_id>[/red]")
        return
    
    try:
        poll_idx = int(args.strip()) - 1  # Convert to 0-based index
        if poll_idx < 0:
            raise ValueError("Poll ID must be positive")
    except ValueError:
        console.print(f"[red]Invalid poll ID: {args}. Expected a number from the polls list.[/red]")
        return
    
    # Get market from cache or fetch
    if 0 <= poll_idx < len(markets_cache):
        market = markets_cache[poll_idx]
    else:
        console.print(f"[yellow]Poll #{poll_idx + 1} not in cache. Run /polls first to see available markets.[/yellow]")
        return
    
    console.print(f"\n[bold cyan]Researching:[/bold cyan] {market.question}")
    console.print(f"[dim]Market ID: {market.id}[/dim]\n")
    
    # Check if research already exists
    existing = research_repo.get_by_market_id(market.id)
    if existing:
        console.print("[yellow]Research already exists for this market. Displaying cached results...[/yellow]\n")
        result, edge, recommendation = existing
        
        # Display cached results
        _display_research_result(
            market=market,
            result=result,
            edge=edge,
            recommendation=recommendation,
            trading_config=trading_config,
        )
        
        # Check if user already made a decision
        decision = research_repo.get_decision(market.id)
        if decision:
            console.print(f"\n[dim]Previous decision: {decision}[/dim]")
            return
        
        # Prompt for trade if recommendation is enter
        if recommendation == "enter":
            _prompt_for_trade(
                market=market,
                result=result,
                research_repo=research_repo,
                trade_repo=trade_repo,
                trading_config=trading_config,
                trading_service=trading_service,
            )
        return
    
    # Run new research
    console.print("[cyan]Starting deep research...[/cyan]\n")
    
    progress_messages = []
    citation_count = 0
    
    def progress_callback(progress: ResearchProgress) -> None:
        """Callback for research progress updates."""
        progress_messages.append(progress.message)
    
    # Run research with live progress display
    with Live(Panel("Initializing research...", title="Research Progress"), refresh_per_second=4) as live:
        def update_callback(progress: ResearchProgress) -> None:
            nonlocal citation_count
            progress_callback(progress)
            
            # Count citations
            if "📎 Found:" in progress.message:
                citation_count += 1
            
            # Show last 15 messages for better context
            recent = progress_messages[-15:]
            
            # Format messages - highlight tool calls and citations
            formatted_messages = []
            for msg in recent:
                if msg.startswith("Round"):
                    formatted_messages.append(f"[cyan]{msg}[/cyan]")
                elif "📎 Found:" in msg:
                    formatted_messages.append(f"[green]{msg}[/green]")
                elif "Thinking..." in msg:
                    formatted_messages.append(f"[yellow]{msg}[/yellow]")
                elif "Usage so far:" in msg:
                    formatted_messages.append(f"[magenta]{msg}[/magenta]")
                else:
                    formatted_messages.append(f"[dim]{msg}[/dim]")
            
            content = "\n".join(formatted_messages)
            content += f"\n\n[bold]Round {progress.round_number}/{progress.total_rounds}[/bold]"
            
            if citation_count > 0:
                content += f" | [green]{citation_count} citations found[/green]"
            
            if progress.completed:
                content += "\n\n[green]✓ Research complete![/green]"
            
            live.update(Panel(content, title="Research Progress", border_style="cyan"))
        
        try:
            result = asyncio.run(research_service.conduct_research(
                market=market,
                callback=update_callback,
            ))
        except Exception as e:
            console.print(f"\n[red]Research failed: {e}[/red]")
            return
    
    console.print("\n[green]✓ Research completed![/green]\n")
    
    # Evaluate position
    evaluation = evaluator.evaluate(market, result)
    
    # Store research results
    research_repo.upsert_result(
        result=result,
        eval_edge=evaluation.edge,
        eval_recommendation=evaluation.recommendation,
    )
    
    # Display results
    _display_research_result(
        market=market,
        result=result,
        edge=evaluation.edge,
        recommendation=evaluation.recommendation,
        trading_config=trading_config,
    )
    
    # Prompt for trade if recommendation is enter
    if evaluation.recommendation == "enter":
        _prompt_for_trade(
            market=market,
            result=result,
            research_repo=research_repo,
            trade_repo=trade_repo,
            trading_config=trading_config,
            trading_service=trading_service,
        )
    else:
        research_repo.set_decision(market.id, "pass")


def _display_research_result(
    market: Market,
    result,
    edge: float,
    recommendation: str,
    trading_config: TradingConfig,
) -> None:
    """Display research results in a formatted panel."""
    
    # Build content
    content = f"[bold]Prediction:[/bold] {result.prediction}\n"
    content += f"[bold]Probability:[/bold] {result.probability:.0%}\n"
    content += f"[bold]Confidence:[/bold] {result.confidence:.0%}\n"
    content += f"[bold]Edge vs Market:[/bold] {edge:+.1%}\n\n"
    content += f"[bold]Rationale:[/bold]\n{result.rationale}\n\n"
    
    if result.key_findings:
        content += f"[bold]Key Findings:[/bold]\n"
        for finding in result.key_findings[:5]:  # Show top 5
            content += f"  • {finding}\n"
        content += "\n"
    
    # Cost info if available
    if result.estimated_cost_usd:
        content += f"[dim]Research cost: ${result.estimated_cost_usd:.4f} | Duration: {result.duration_minutes} min[/dim]\n"
    
    # Recommendation
    if recommendation == "enter":
        market_odds = market.formatted_odds()
        odds = market_odds.get(result.prediction, 0.5)
        payout_str = format_payout(trading_config.default_stake, odds)
        
        content += f"\n[bold green]RECOMMENDATION: ENTER[/bold green]\n"
        content += f"Bet on: {result.prediction} at {odds:.0%}\n"
        content += f"Potential payout for ${trading_config.default_stake:.0f}: {payout_str}"
    else:
        content += f"\n[bold yellow]RECOMMENDATION: PASS[/bold yellow]\n"
        content += "Edge or confidence threshold not met."
    
    console.print(Panel(content, title="Research Results", border_style="green"))


def _prompt_for_trade(
    market: Market,
    result,
    research_repo: ResearchRepository,
    trade_repo: TradeRepository,
    trading_config: TradingConfig,
    trading_service: TradingService | None,
) -> None:
    """Prompt user to enter trade (paper or real based on config)."""
    
    # Determine trading mode
    is_real_mode = trading_config.mode == "real"
    
    # Get current odds
    market_odds = market.formatted_odds()
    odds = market_odds.get(result.prediction, 0.5)
    
    # Find the outcome token
    outcome_token = None
    for outcome in market.outcomes:
        if outcome.outcome == result.prediction:
            outcome_token = outcome
            break
    
    if not outcome_token:
        console.print("[red]Error: Could not find outcome token[/red]")
        return
    
    # Get available balance
    available_balance = get_available_balance(trading_config, trade_repo, trading_service)
    
    # Prompt for amount with balance and payout display
    amount = prompt_for_amount(
        available_balance=available_balance,
        default_stake=trading_config.default_stake,
        market_question=market.question,
        outcome_name=result.prediction,
        outcome_price=odds,
        is_real_mode=is_real_mode,
    )
    
    if amount is None:
        console.print("[yellow]Trade cancelled.[/yellow]")
        research_repo.set_decision(market.id, "pass")
        return
    
    # Handle real trading mode
    if is_real_mode:
        if not trading_service:
            console.print("[red]Error: Trading service not available. Check POLYGON_PRIVATE_KEY.[/red]")
            return
        
        # Final confirmation for real money
        console.print(Panel(f"[bold red]⚠️  REAL MONEY TRADE[/bold red]", style="red"))
        if not Confirm.ask("Execute real trade?", default=False):
            console.print("[yellow]Trade cancelled.[/yellow]")
            research_repo.set_decision(market.id, "pass")
            return
        
        # Calculate shares
        estimated_shares = amount / odds if odds > 0 else 0
        
        # Execute real trade
        console.print("\n[dim]Executing trade...[/dim]")
        trade_result = trading_service.execute_market_buy(outcome_token.token_id, estimated_shares)
        
        if not trade_result.success:
            console.print(f"[red]✗ Trade failed: {trade_result.error}[/red]")
            research_repo.set_decision(market.id, "pass")
            return
        
        # Create trade record with real execution details
        trade = Trade(
            id=None,
            market_id=market.id,
            question=market.question,
            category=market.category,
            selected_option=result.prediction,
            entry_odds=trade_result.executed_price,
            stake_amount=amount,
            entry_timestamp=datetime.now(tz=timezone.utc),
            predicted_probability=result.probability,
            confidence=result.confidence,
            research_id=None,
            status="active",
            resolves_at=market.end_date,
            actual_outcome=None,
            profit_loss=None,
            closed_at=None,
            trade_mode="real",
            order_id=trade_result.order_id,
        )
        
        saved_trade = trade_repo.record_trade(trade)
        research_repo.set_decision(market.id, "enter")
        
        console.print(f"\n[green]✓ REAL trade executed! Position ID: {saved_trade.id}[/green]")
        console.print(f"[dim]Order ID: {trade_result.order_id}[/dim]")
        console.print(f"[dim]Executed Price: ${trade_result.executed_price:.3f}[/dim]")
        console.print(f"[dim]Shares: {trade_result.executed_size:.2f}[/dim]")
        console.print(f"[dim]Stake: ${amount:.2f} | Expires: {market.end_date.strftime('%Y-%m-%d')}[/dim]")
    
    else:
        # Paper trading mode - confirm with simple yes/no
        console.print(Panel(f"[bold green]PAPER TRADE[/bold green]", style="green"))
        if not Confirm.ask("Enter paper trade?", default=True):
            console.print("[yellow]Trade cancelled.[/yellow]")
            research_repo.set_decision(market.id, "pass")
            return
        
        # Paper trading
        trade = Trade(
            id=None,
            market_id=market.id,
            question=market.question,
            category=market.category,
            selected_option=result.prediction,
            entry_odds=odds,
            stake_amount=amount,
            entry_timestamp=datetime.now(tz=timezone.utc),
            predicted_probability=result.probability,
            confidence=result.confidence,
            research_id=None,
            status="active",
            resolves_at=market.end_date,
            actual_outcome=None,
            profit_loss=None,
            closed_at=None,
            trade_mode="paper",
            order_id=None,
        )
        
        # Record paper trade
        saved_trade = trade_repo.record_trade(trade)
        research_repo.set_decision(market.id, "enter")
        
        console.print(f"\n[green]✓ Paper trade recorded! Position ID: {saved_trade.id}[/green]")
        console.print(f"[dim]Stake: ${trade.stake_amount:.2f} | Odds: {odds:.0%} | Expires: {market.end_date.strftime('%Y-%m-%d')}[/dim]")

