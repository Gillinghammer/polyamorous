"""Research command handler for Polly CLI."""

import asyncio
from datetime import datetime, timezone
from typing import List

from rich.console import Console
from rich.live import Live
from rich.panel import Panel

from polly.config import PaperTradingConfig, ResearchConfig
from polly.models import Market, ResearchProgress, Trade
from polly.services.evaluator import PositionEvaluator
from polly.services.polymarket import PolymarketService
from polly.services.research import ResearchService
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
    paper_config: PaperTradingConfig,
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
        paper_config: Paper trading configuration
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
            paper_config=paper_config,
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
                paper_config=paper_config,
            )
        return
    
    # Run new research
    console.print("[cyan]Starting deep research... This may take 20-40 minutes.[/cyan]\n")
    
    progress_messages = []
    
    def progress_callback(progress: ResearchProgress) -> None:
        """Callback for research progress updates."""
        progress_messages.append(progress.message)
    
    # Run research with live progress display
    with Live(Panel("Initializing research...", title="Research Progress"), refresh_per_second=2) as live:
        def update_callback(progress: ResearchProgress) -> None:
            progress_callback(progress)
            
            # Build content with recent messages
            recent = progress_messages[-5:]  # Last 5 messages
            content = "\n".join(f"[dim]{msg}[/dim]" for msg in recent[:-1])
            if recent:
                content += f"\n\n[bold]{recent[-1]}[/bold]"
            content += f"\n\n[cyan]Round {progress.round_number}/{progress.total_rounds}[/cyan]"
            
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
        paper_config=paper_config,
    )
    
    # Prompt for trade if recommendation is enter
    if evaluation.recommendation == "enter":
        _prompt_for_trade(
            market=market,
            result=result,
            research_repo=research_repo,
            trade_repo=trade_repo,
            paper_config=paper_config,
        )
    else:
        research_repo.set_decision(market.id, "pass")


def _display_research_result(
    market: Market,
    result,
    edge: float,
    recommendation: str,
    paper_config: PaperTradingConfig,
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
        payout_str = format_payout(paper_config.default_stake, odds)
        
        content += f"\n[bold green]RECOMMENDATION: ENTER[/bold green]\n"
        content += f"Bet on: {result.prediction} at {odds:.0%}\n"
        content += f"Potential payout for ${paper_config.default_stake:.0f}: {payout_str}"
    else:
        content += f"\n[bold yellow]RECOMMENDATION: PASS[/bold yellow]\n"
        content += "Edge or confidence threshold not met."
    
    console.print(Panel(content, title="Research Results", border_style="green"))


def _prompt_for_trade(
    market: Market,
    result,
    research_repo: ResearchRepository,
    trade_repo: TradeRepository,
    paper_config: PaperTradingConfig,
) -> None:
    """Prompt user to enter trade."""
    
    console.print(f"\n[bold]Enter trade with ${paper_config.default_stake:.0f} stake? (y/n):[/bold] ", end="")
    
    try:
        response = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Trade cancelled.[/yellow]")
        return
    
    if response == "y":
        # Get current odds
        market_odds = market.formatted_odds()
        odds = market_odds.get(result.prediction, 0.5)
        
        # Create trade
        trade = Trade(
            id=None,
            market_id=market.id,
            question=market.question,
            category=market.category,
            selected_option=result.prediction,
            entry_odds=odds,
            stake_amount=paper_config.default_stake,
            entry_timestamp=datetime.now(tz=timezone.utc),
            predicted_probability=result.probability,
            confidence=result.confidence,
            research_id=None,
            status="active",
            resolves_at=market.end_date,
            actual_outcome=None,
            profit_loss=None,
            closed_at=None,
        )
        
        # Record trade
        saved_trade = trade_repo.record_trade(trade)
        research_repo.set_decision(market.id, "enter")
        
        console.print(f"\n[green]✓ Trade recorded! Position ID: {saved_trade.id}[/green]")
        console.print(f"[dim]Stake: ${trade.stake_amount:.2f} | Odds: {odds:.0%} | Expires: {market.end_date.strftime('%Y-%m-%d')}[/dim]")
    else:
        research_repo.set_decision(market.id, "pass")
        console.print("\n[yellow]Trade declined.[/yellow]")

