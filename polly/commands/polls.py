"""Polls command handler for Polly CLI."""

import asyncio
from typing import List

from rich.console import Console

from polly.models import Market
from polly.services.polymarket import PolymarketService, filter_by_expiry_days
from polly.ui.formatters import create_polls_table

console = Console()


def handle_polls(args: str, polymarket: PolymarketService) -> List[Market]:
    """Handle /polls [days] [search_term] command.
    
    Args:
        args: Command arguments (e.g., "7", "bitcoin", "7 bitcoin", "14 trump")
        polymarket: Polymarket service instance
        
    Returns:
        List of markets for reference by other commands
    """
    # Parse arguments: [days] [search_term]
    days_filter = None
    search_term = None
    
    if args.strip():
        parts = args.strip().split(maxsplit=1)
        
        # First part could be days (number) or search term
        if parts[0].isdigit():
            days_num = int(parts[0])
            if days_num in (7, 14, 30, 180):
                days_filter = days_num
                # Second part (if exists) is search term
                if len(parts) > 1:
                    search_term = parts[1]
            else:
                console.print(f"[red]Invalid days filter: {days_num}. Use 7, 14, 30, or 180.[/red]")
                return []
        else:
            # First part is search term, no days filter
            search_term = args.strip()
    
    # Fetch markets
    console.print("[cyan]Fetching markets from Polymarket...[/cyan]")
    try:
        markets = asyncio.run(polymarket.fetch_all_markets())
    except Exception as e:
        console.print(f"[red]Error fetching markets: {e}[/red]")
        return []
    
    if not markets:
        console.print("[yellow]No markets found.[/yellow]")
        return []
    
    # Apply time filter if specified
    if days_filter:
        markets = filter_by_expiry_days(markets, days_filter)
        if not markets:
            console.print(f"[yellow]No markets found expiring within {days_filter} days.[/yellow]")
            return []
    
    # Apply search filter if specified
    if search_term:
        search_lower = search_term.lower()
        markets = [
            m for m in markets
            if search_lower in m.question.lower()
            or search_lower in m.description.lower()
            or search_lower in (m.category or "").lower()
            or any(search_lower in tag.lower() for tag in m.tags)
        ]
        if not markets:
            console.print(f"[yellow]No markets found matching '{search_term}'.[/yellow]")
            return []
    
    # Sort by expiry date (soonest first)
    markets = sorted(markets, key=lambda m: m.end_date)
    
    # Display results
    table = create_polls_table(markets[:20])  # Limit to top 20
    console.print(table)
    
    # Build status message
    status_parts = []
    if days_filter:
        status_parts.append(f"expiring in {days_filter} days")
    if search_term:
        status_parts.append(f"matching '{search_term}'")
    status_msg = " and ".join(status_parts) if status_parts else "sorted by expiry date"
    
    console.print(f"\n[dim]Showing {len(markets[:20])} of {len(markets)} markets ({status_msg})[/dim]")
    console.print("[dim]Use poll ID (1-20) with /research command[/dim]")
    
    return markets[:20]  # Return limited list for indexing

