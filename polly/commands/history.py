"""History command handler for Polly CLI."""

import asyncio
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from polly.services.polymarket import PolymarketService
from polly.storage.research import ResearchRepository

console = Console()


def handle_history(args: str, research_repo: ResearchRepository, polymarket: PolymarketService) -> None:
    """Handle /history [status] command.
    
    Args:
        args: Status filter (completed, pending, archived, or empty for all)
        research_repo: Research repository instance
        polymarket: Polymarket service instance
    """
    status_filter = args.strip().lower() if args.strip() else "all"
    
    if status_filter not in ("all", "completed", "pending", "archived"):
        console.print(f"[red]Invalid status: {status_filter}. Use: completed, pending, archived, or leave empty for all.[/red]")
        return
    
    try:
        # Get research records
        if status_filter == "all":
            records = research_repo.list(decision="all")
        elif status_filter == "completed":
            records = research_repo.list(decision="decided")
        elif status_filter == "pending":
            records = research_repo.list(decision="undecided")
        else:  # archived - need to check market expiry
            records = research_repo.list(decision="all")
        
        if not records:
            console.print(f"[yellow]No research found for status: {status_filter}[/yellow]")
            return
        
        # Fetch markets to get questions and check archived status
        market_ids = [r["market_id"] for r in records]
        markets_dict = {}
        try:
            markets = asyncio.run(polymarket.fetch_markets_by_ids(market_ids))
            markets_dict = {m.id: m for m in markets}
        except Exception as e:
            console.print(f"[yellow]Warning: Could not fetch market details: {e}[/yellow]")
        
        # Filter for archived status
        if status_filter == "archived":
            now = datetime.now(tz=timezone.utc)
            records = [
                r for r in records
                if r["market_id"] in markets_dict and markets_dict[r["market_id"]].end_date < now
            ]
        
        if not records:
            console.print(f"[yellow]No research found for status: {status_filter}[/yellow]")
            return
        
        # Create table
        table = Table(title=f"Research History ({status_filter.title()})", show_header=True, header_style="bold cyan")
        
        table.add_column("Market ID", style="dim", width=40)
        table.add_column("Question", style="white", width=50)
        table.add_column("Recommendation", style="yellow", width=15)
        table.add_column("Edge", style="magenta", width=10)
        table.add_column("Decision", style="green", width=10)
        
        for record in records:
            market_id = record["market_id"]
            market = markets_dict.get(market_id)
            question = market.question if market else market_id
            
            # Truncate question if too long
            if len(question) > 47:
                question = question[:44] + "..."
            
            rec = record.get("rec", "N/A")
            edge = record.get("edge", 0.0)
            edge_str = f"{edge:+.1%}" if edge else "N/A"
            decision = record.get("decision") or "Pending"
            
            table.add_row(
                market_id[:40],
                question,
                rec.upper(),
                edge_str,
                decision
            )
        
        console.print(table)
        console.print(f"\n[dim]Showing {len(records)} research result(s)[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error loading history: {e}[/red]")

