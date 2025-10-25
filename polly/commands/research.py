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
from polly.models import Market, MarketGroup, ResearchProgress, ResearchResult, Trade
from polly.services.evaluator import PositionEvaluator
from polly.services.polymarket import PolymarketService
from polly.services.research import ResearchService, calculate_optimal_rounds
from polly.services.trading import TradingService
from polly.services.validators import check_usdc_balance, validate_market_active
from polly.storage.research import ResearchRepository
from polly.storage.trades import TradeRepository
from polly.ui.formatters import format_payout

console = Console()


def handle_research(
    args: str,
    markets_cache: List[Market | MarketGroup],
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
    
    # Get item from cache
    if 0 <= poll_idx < len(markets_cache):
        item = markets_cache[poll_idx]
    else:
        console.print(f"[yellow]Poll #{poll_idx + 1} not in cache. Run /polls first to see available items.[/yellow]")
        return
    
    # Check if it's a grouped event or individual market
    if isinstance(item, MarketGroup):
        _handle_group_research(
            group=item,
            research_service=research_service,
            evaluator=evaluator,
            research_repo=research_repo,
            trade_repo=trade_repo,
            research_config=research_config,
            trading_config=trading_config,
            trading_service=trading_service,
        )
        return
    
    # Individual market research (existing flow)
    market = item
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
    content += f"[bold]Confidence:[/bold] {int(result.confidence)}%\n"
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


def _handle_group_research(
    group: MarketGroup,
    research_service: ResearchService,
    evaluator: PositionEvaluator,
    research_repo: ResearchRepository,
    trade_repo: TradeRepository,
    research_config: ResearchConfig,
    trading_config: TradingConfig,
    trading_service: TradingService | None,
) -> None:
    """Handle research for a grouped multi-outcome event."""
    
    console.print(f"\n[bold cyan]Researching Grouped Event:[/bold cyan] {group.title}")
    console.print(f"[dim]Event ID: {group.id} | {len(group.markets)} markets | ${group.liquidity:,.0f} liquidity[/dim]\n")
    
    # Show top candidates
    console.print("[cyan]Top candidates by winning probability:[/cyan]")
    top_markets = group.get_top_markets(10)
    for i, market in enumerate(top_markets, 1):
        # Get Yes probability (winning chance)
        yes_prob = next((o.price for o in market.outcomes if o.outcome.lower() in ('yes', 'y')), 0.0)
        candidate = market.question.split("Will ")[-1].split(" win")[0] if "Will " in market.question else market.question[:40]
        console.print(f"  {i}. {candidate}: {yes_prob:.1%}")
    
    if len(group.markets) > 10:
        console.print(f"  ... and {len(group.markets) - 10} more\n")
    else:
        console.print()
    
    # Check if research already exists
    existing = research_repo.get_by_market_id(group.id)
    if existing:
        console.print("[yellow]Research already exists for this event. Displaying cached results...[/yellow]\n")
        result, edge, recommendation = existing
        _display_group_research_result(group, result, trading_config)
        
        # Check if user already made a decision
        decision = research_repo.get_decision(group.id)
        if decision:
            console.print(f"\n[dim]Previous decision: {decision}[/dim]")
            return
        
        # Prompt for trades if recommendations exist
        if result.recommendations:
            _prompt_for_group_trades(
                group=group,
                result=result,
                research_repo=research_repo,
                trade_repo=trade_repo,
                trading_config=trading_config,
            )
        return
    
    # Calculate optimal rounds for this event
    optimal_rounds = calculate_optimal_rounds(group)
    console.print(f"[dim]Adaptive research: {optimal_rounds} rounds planned based on event complexity[/dim]\n")
    
    # Run new group research
    console.print("[cyan]Starting deep multi-outcome research...[/cyan]\n")
    
    progress_messages = []
    
    def progress_callback(progress: ResearchProgress) -> None:
        """Callback for research progress updates."""
        progress_messages.append(progress.message)
    
    # Run research with live progress display
    with Live(Panel("Initializing group research...", title="Research Progress"), refresh_per_second=4) as live:
        def update_callback(progress: ResearchProgress) -> None:
            progress_callback(progress)
            
            # Show last 15 messages
            recent = progress_messages[-15:]
            formatted_messages = []
            for msg in recent:
                if msg.startswith("Round"):
                    formatted_messages.append(f"[cyan]{msg}[/cyan]")
                elif "🔍" in msg:
                    formatted_messages.append(f"[green]{msg}[/green]")
                else:
                    formatted_messages.append(f"[dim]{msg}[/dim]")
            
            content = "\n".join(formatted_messages)
            content += f"\n\n[bold]Round {progress.round_number}/{progress.total_rounds}[/bold]"
            
            if progress.completed:
                content += "\n\n[green]✓ Group research complete![/green]"
            
            live.update(Panel(content, title="Group Research Progress", border_style="cyan"))
        
        try:
            result = asyncio.run(research_service.research_market_group(
                group=group,
                callback=update_callback,
                rounds=optimal_rounds,
            ))
            console.print("[dim]Research method returned successfully[/dim]")
        except Exception as e:
            console.print(f"\n[red]Research failed: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return
    
    # Force output to appear after Live context closes
    import time
    time.sleep(0.2)  # Longer pause to ensure Live is fully closed
    console.print("\n")  # Extra newline for separation
    
    console.print("[green]✓ Group research completed![/green]\n")
    
    # Show research quality metrics
    console.print(f"[cyan]Research Quality:[/cyan]")
    console.print(f"  Rounds: {result.rounds_completed}/{optimal_rounds}")
    console.print(f"  Citations: {len(result.citations)} total")
    console.print(f"  Recommendations: {len(result.recommendations)} positions")
    if result.estimated_cost_usd:
        console.print(f"  Cost: ${result.estimated_cost_usd:.4f}")
    console.print()
    
    try:
        # Store research results
        research_repo.upsert_result(
            result=result,
            eval_edge=0.0,  # Group edge calculated differently
            eval_recommendation="review",  # User reviews recommendations
        )
    except Exception as e:
        console.print(f"[yellow]Warning: Could not store results: {e}[/yellow]\n")
    
    # Display results (with explicit error handling)
    console.print("[dim]Preparing to display results...[/dim]\n")
    
    try:
        _display_group_research_result(group, result, trading_config)
        console.print("[dim]Results displayed successfully[/dim]\n")
    except Exception as e:
        console.print(f"[red]Error displaying results: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return
    
    try:
        # Validate research quality
        _validate_research_quality(group, result)
        console.print("[dim]Quality validation complete[/dim]\n")
    except Exception as e:
        console.print(f"[yellow]Warning: Quality validation failed: {e}[/yellow]\n")
    
    # Prompt for trades if recommendations exist
    if result.recommendations:
        try:
            _prompt_for_group_trades(
                group=group,
                result=result,
                research_repo=research_repo,
                trade_repo=trade_repo,
                trading_config=trading_config,
            )
        except Exception as e:
            console.print(f"[red]Error prompting for trades: {e}[/red]")
    else:
        console.print("\n[yellow]No recommendations generated. Marking as pass.[/yellow]")
        try:
            research_repo.set_decision(group.id, "pass")
        except Exception:
            pass


def _display_group_research_result(
    group: MarketGroup,
    result: ResearchResult,
    trading_config: TradingConfig,
) -> None:
    """Display research results for a grouped event."""
    
    content = f"[bold]Event:[/bold] {group.title}\n"
    content += f"[bold]Total Markets:[/bold] {len(group.markets)}\n\n"
    
    if result.recommendations:
        total_suggested_stake = sum(r.suggested_stake for r in result.recommendations if r.entry_suggested)
        content += f"[bold green]RECOMMENDATIONS ({len(result.recommendations)} positions):[/bold green]\n"
        if total_suggested_stake > 0:
            content += f"[dim]Total portfolio allocation: ${total_suggested_stake:.0f}[/dim]\n\n"
        
        for i, rec in enumerate(result.recommendations, 1):
            # Extract candidate/party name from question
            question = rec.market_question
            if "Will " in question and " win" in question:
                candidate = question.split("Will ")[-1].split(" win")[0].strip()
            elif " - " in question:
                candidate = question.split(" - ")[0].strip()
            else:
                # Try to find the unique part of the question
                candidate = question.replace(group.title, "").strip().split(":")[0][:40]
            
            # Find market to get current odds - try multiple matching strategies
            market = next((m for m in group.markets if m.id == rec.market_id), None)
            
            # If not found by ID, try matching by question similarity
            if not market and candidate:
                market = next((m for m in group.markets if candidate.lower() in m.question.lower()), None)
            
            current_odds = 0.0
            if market:
                current_odds = next((o.price for o in market.outcomes if o.outcome.lower() in ('yes', 'y')), 0.0)
            
            content += f"{i}. [bold]{candidate}[/bold] - {rec.prediction}\n"
            content += f"   Win Probability: {rec.probability:.1%} | Current Odds: {current_odds:.1%} | Confidence: {int(rec.confidence)}%\n"
            
            if rec.entry_suggested:
                pct_of_portfolio = (rec.suggested_stake / total_suggested_stake * 100) if total_suggested_stake > 0 else 0
                content += f"   [green]✓ ENTER: ${rec.suggested_stake:.0f} ({pct_of_portfolio:.0f}% of portfolio)[/green]\n"
                
                # Calculate expected value
                if current_odds > 0:
                    shares = rec.suggested_stake / current_odds
                    ev = (rec.probability * shares) - ((1 - rec.probability) * rec.suggested_stake)
                    content += f"   Expected Value: [cyan]${ev:+.2f}[/cyan]\n"
            else:
                content += f"   [yellow]○ Analyze only (no entry suggested)[/yellow]\n"
            
            content += f"   {rec.rationale[:120]}...\n\n"
    else:
        content += "[yellow]No specific recommendations generated yet.[/yellow]\n"
        content += f"[dim]This feature is under development.[/dim]\n"
    
    content += f"\n[bold]Overall Analysis:[/bold]\n{result.rationale[:200]}...\n\n"
    
    if result.key_findings:
        content += f"[bold]Key Findings:[/bold]\n"
        for finding in result.key_findings[:3]:
            content += f"  • {finding}\n"
    
    if result.estimated_cost_usd:
        content += f"\n[dim]Research cost: ${result.estimated_cost_usd:.4f} | Duration: {result.duration_minutes} min[/dim]"
    
    console.print(Panel(content, title="Group Research Results", border_style="green"))


def _prompt_for_group_trades(
    group: MarketGroup,
    result: ResearchResult,
    research_repo: ResearchRepository,
    trade_repo: TradeRepository,
    trading_config: TradingConfig,
) -> None:
    """Prompt user to enter multiple positions from group research."""
    
    # Filter to only entry-suggested recommendations
    suggested = [r for r in result.recommendations if r.entry_suggested]
    
    if not suggested:
        console.print("\n[yellow]No positions recommended for entry.[/yellow]")
        research_repo.set_decision(group.id, "pass")
        return
    
    console.print(f"\n[bold]Research suggests {len(suggested)} position(s):[/bold]")
    console.print("[dim]Portfolio-optimized strategy with varying position sizes:[/dim]\n")
    
    total_stake = sum(rec.suggested_stake for rec in suggested)
    total_ev = 0.0
    
    for i, rec in enumerate(suggested, 1):
        # Extract candidate/party name
        question = rec.market_question
        if "Will " in question and " win" in question:
            candidate = question.split("Will ")[-1].split(" win")[0].strip()
        elif " - " in question:
            candidate = question.split(" - ")[0].strip()
        else:
            candidate = question.replace(group.title, "").strip().split(":")[0][:40]
        
        # Find market to get current odds - try multiple matching strategies
        market = next((m for m in group.markets if m.id == rec.market_id), None)
        if not market and candidate:
            market = next((m for m in group.markets if candidate.lower() in m.question.lower()), None)
        if market:
            # Get Yes probability (winning odds)
            odds = next((o.price for o in market.outcomes if o.outcome.lower() in ('yes', 'y')), 0.5)
            
            # Calculate EV and potential payout
            shares = rec.suggested_stake / odds if odds > 0 else 0
            payout = shares * 1.0  # Binary contracts pay $1 per share
            ev = (rec.probability * shares) - ((1 - rec.probability) * rec.suggested_stake)
            total_ev += ev
            
            pct_of_portfolio = (rec.suggested_stake / total_stake * 100) if total_stake > 0 else 0
            
            console.print(f"  {i}. [cyan]{candidate}[/cyan] {rec.prediction} @ {odds:.1%}")
            console.print(f"     Stake: [bold]${rec.suggested_stake:.0f}[/bold] ({pct_of_portfolio:.0f}% of portfolio)")
            console.print(f"     Potential: ${payout:.0f} | EV: ${ev:+.2f}")
    
    console.print(f"\n[bold]Portfolio Summary:[/bold]")
    console.print(f"  Total Stake: ${total_stake:.0f}")
    console.print(f"  Combined EV: [cyan]${total_ev:+.2f}[/cyan]")
    
    # Calculate ROI
    roi = (total_ev / total_stake * 100) if total_stake > 0 else 0
    console.print(f"  Portfolio ROI: [cyan]{roi:+.1f}%[/cyan]")
    console.print(f"  Strategy: Diversified hedge across {len(suggested)} positions")
    
    # For now, just record decision
    console.print("\n[yellow]⚠️  Multi-position entry not yet implemented.[/yellow]")
    console.print("[yellow]Paper trading for grouped events coming soon![/yellow]")
    research_repo.set_decision(group.id, "review")


def _validate_research_quality(group: MarketGroup, result: ResearchResult) -> None:
    """Validate research quality and show warnings if metrics are low."""
    
    warnings = []
    successes = []
    
    # Check citation count
    if len(result.citations) >= 10:
        successes.append(f"✓ Good citation count ({len(result.citations)})")
    elif len(result.citations) >= 5:
        warnings.append(f"⚠ Low citation count ({len(result.citations)}, target: 10+)")
    else:
        warnings.append(f"⚠ Very low citations ({len(result.citations)}, needs improvement)")
    
    # Check if found edge
    if result.recommendations:
        edges = []
        for rec in result.recommendations:
            # Find market
            market = next((m for m in group.markets if m.id == rec.market_id), None)
            if market:
                current = next((o.price for o in market.outcomes if o.outcome.lower() in ('yes', 'y')), 0.0)
                edge = abs(rec.probability - current)
                edges.append(edge)
        
        max_edge = max(edges) if edges else 0.0
        if max_edge > 0.15:
            successes.append(f"✓ Found strong edge ({max_edge:.1%})")
        elif max_edge > 0.10:
            successes.append(f"✓ Found moderate edge ({max_edge:.1%})")
        else:
            warnings.append(f"⚠ Weak edge found ({max_edge:.1%}, may not justify entry)")
    
    # Check recommendations count
    entry_count = sum(1 for r in result.recommendations if r.entry_suggested)
    if entry_count >= 2:
        successes.append(f"✓ Multi-position hedge ({entry_count} positions)")
    elif entry_count == 1:
        warnings.append("⚠ Single position only (no hedge diversification)")
    else:
        warnings.append("⚠ No entry recommendations (no edge found)")
    
    # Check confidence
    if result.confidence >= 80:
        successes.append(f"✓ High confidence ({result.confidence:.0f}%)")
    elif result.confidence >= 60:
        successes.append(f"○ Moderate confidence ({result.confidence:.0f}%)")
    else:
        warnings.append(f"⚠ Low confidence ({result.confidence:.0f}%)")
    
    # Display validation results
    if successes or warnings:
        console.print("\n[bold]Research Quality Assessment:[/bold]")
        for success in successes:
            console.print(f"  {success}")
        for warning in warnings:
            console.print(f"  [yellow]{warning}[/yellow]")
        console.print()

