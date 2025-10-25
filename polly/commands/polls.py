"""Polls command handler for Polly CLI."""

import asyncio
from typing import List, Union

from rich.console import Console

from polly.models import Market, MarketGroup
from polly.services.polymarket import PolymarketService, filter_by_expiry_days
from polly.ui.formatters import create_polls_table

console = Console()


def handle_polls(args: str, polymarket: PolymarketService) -> List[Union[Market, MarketGroup]]:
    """Handle /polls [days] [search_term] [-asc|-dsc column] [-odds max] command.
    
    Args:
        args: Command arguments (e.g., "7", "bitcoin", "7 bitcoin -dsc expires", "tesla -odds 50")
        polymarket: Polymarket service instance
        
    Returns:
        List of markets/groups for reference by other commands
    """
    # Parse arguments: [days] [search_term] [-asc|-dsc column] [-odds max]
    days_filter = None
    search_term = None
    sort_direction = None  # 'asc' or 'dsc'
    sort_column = None
    max_odds = None
    
    if args.strip():
        parts = args.strip().split()
        remaining_parts = []
        
        # Extract flags
        i = 0
        while i < len(parts):
            part_lower = parts[i].lower()
            if part_lower in ('-asc', '-dsc'):
                sort_direction = 'asc' if part_lower == '-asc' else 'dsc'
                # Next part should be column name
                if i + 1 < len(parts) and not parts[i + 1].startswith('-'):
                    sort_column = parts[i + 1].lower()
                    i += 2
                else:
                    console.print(f"[red]Sort flag {parts[i]} requires a column name (category, question, odds, expires, liquidity)[/red]")
                    return []
            elif part_lower == '-odds':
                # Next part should be max odds value
                if i + 1 < len(parts) and not parts[i + 1].startswith('-'):
                    try:
                        max_odds = int(parts[i + 1])
                        if max_odds < 1 or max_odds > 99:
                            console.print("[red]Odds value must be between 1 and 99[/red]")
                            return []
                        i += 2
                    except ValueError:
                        console.print(f"[red]Invalid odds value: {parts[i + 1]}. Must be a number between 1 and 99.[/red]")
                        return []
                else:
                    console.print("[red]-odds flag requires a value (1-99)[/red]")
                    return []
            else:
                remaining_parts.append(parts[i])
                i += 1
        
        # Parse remaining parts: [days] [search_term]
        if remaining_parts:
            # First part could be days (number) or search term
            if remaining_parts[0].isdigit():
                days_num = int(remaining_parts[0])
                if days_num in (7, 14, 30, 180):
                    days_filter = days_num
                    # Remaining parts are search term
                    if len(remaining_parts) > 1:
                        search_term = ' '.join(remaining_parts[1:])
                else:
                    console.print(f"[red]Invalid days filter: {days_num}. Use 7, 14, 30, or 180.[/red]")
                    return []
            else:
                # All parts are search term
                search_term = ' '.join(remaining_parts)
    
    # Fetch markets and groups
    console.print("[cyan]Fetching markets from Polymarket...[/cyan]")
    try:
        items = asyncio.run(polymarket.fetch_all_markets())
    except Exception as e:
        console.print(f"[red]Error fetching markets: {e}[/red]")
        return []
    
    if not items:
        console.print("[yellow]No markets found.[/yellow]")
        return []
    
    # Apply time filter if specified
    if days_filter:
        items = filter_by_expiry_days(items, days_filter)
        if not items:
            console.print(f"[yellow]No items found expiring within {days_filter} days.[/yellow]")
            return []
    
    # Apply search filter if specified
    if search_term:
        search_lower = search_term.lower()
        filtered_items = []
        for item in items:
            if isinstance(item, MarketGroup):
                # Search in group title, description, category, and tags
                if (search_lower in item.title.lower()
                    or search_lower in item.description.lower()
                    or search_lower in item.category.lower()
                    or any(search_lower in tag.lower() for tag in item.tags)):
                    filtered_items.append(item)
            else:
                # Market search (existing logic)
                if (search_lower in item.question.lower()
                    or search_lower in item.description.lower()
                    or search_lower in (item.category or "").lower()
                    or any(search_lower in tag.lower() for tag in item.tags)):
                    filtered_items.append(item)
        items = filtered_items
        if not items:
            console.print(f"[yellow]No items found matching '{search_term}'.[/yellow]")
            return []
    
    # Apply odds filter if specified
    if max_odds is not None:
        max_odds_decimal = max_odds / 100.0
        filtered_items = []
        for item in items:
            if isinstance(item, MarketGroup):
                # For groups, check if any market has odds within threshold
                has_valid_odds = any(
                    max(o.price for o in m.outcomes) <= max_odds_decimal
                    for m in item.markets if m.outcomes
                )
                if has_valid_odds:
                    filtered_items.append(item)
            else:
                # Market (existing logic)
                if item.outcomes and max(o.price for o in item.outcomes) <= max_odds_decimal:
                    filtered_items.append(item)
        items = filtered_items
        if not items:
            console.print(f"[yellow]No items found with maximum odds at or below {max_odds}%.[/yellow]")
            return []
    
    # Apply sorting
    if sort_column:
        # Validate column name
        valid_columns = ['category', 'question', 'odds', 'expires', 'liquidity']
        if sort_column not in valid_columns:
            console.print(f"[red]Invalid column: {sort_column}. Choose from: {', '.join(valid_columns)}[/red]")
            return []
        
        # Define sort key based on column (handle both Market and MarketGroup)
        if sort_column == 'category':
            sort_key = lambda item: (item.category or "").lower()
        elif sort_column == 'question':
            sort_key = lambda item: (item.title if isinstance(item, MarketGroup) else item.question).lower()
        elif sort_column == 'odds':
            # For groups, use best market odds; for markets, use max odds
            def odds_key(item):
                if isinstance(item, MarketGroup):
                    return max((max(o.price for o in m.outcomes) for m in item.markets if m.outcomes), default=0)
                else:
                    return max((o.price for o in item.outcomes), default=0) if item.outcomes else 0
            sort_key = odds_key
        elif sort_column == 'expires':
            sort_key = lambda item: item.end_date
        elif sort_column == 'liquidity':
            sort_key = lambda item: item.liquidity
        
        reverse = (sort_direction == 'dsc')
        items = sorted(items, key=sort_key, reverse=reverse)
    else:
        # Default: sort by expiry date (soonest first)
        items = sorted(items, key=lambda item: item.end_date)
    
    # Display results
    table = create_polls_table(items[:20])  # Limit to top 20
    console.print(table)
    
    # Build status message
    status_parts = []
    if days_filter:
        status_parts.append(f"expiring in {days_filter} days")
    if search_term:
        status_parts.append(f"matching '{search_term}'")
    if max_odds is not None:
        status_parts.append(f"max odds ≤{max_odds}%")
    
    # Add sort info
    if sort_column:
        sort_dir_text = "ascending" if sort_direction == "asc" else "descending"
        status_parts.append(f"sorted by {sort_column} ({sort_dir_text})")
    else:
        status_parts.append("sorted by expiry date")
    
    status_msg = ", ".join(status_parts) if status_parts else "all items"
    
    console.print(f"\n[dim]Showing {len(items[:20])} of {len(items)} items ({status_msg})[/dim]")
    console.print("[dim]Use poll ID (1-20) with /research command[/dim]")
    
    return items[:20]  # Return limited list for indexing


def show_group_detail(group: MarketGroup, show_all: bool = False) -> None:
    """Display detailed view of all markets in a grouped event.
    
    Args:
        group: The MarketGroup to display
        show_all: If True, show all markets; if False, show top 20
    """
    from rich.table import Table
    
    console.print(f"\n[bold cyan]Event:[/bold cyan] {group.title}")
    console.print(f"[dim]{group.description}[/dim]\n" if group.description else "")
    console.print(f"[bold]Category:[/bold] {group.category}")
    console.print(f"[bold]Total Markets:[/bold] {len(group.markets)}")
    console.print(f"[bold]Total Liquidity:[/bold] ${group.liquidity:,.0f}")
    console.print(f"[bold]Volume 24h:[/bold] ${group.volume_24h:,.0f}")
    console.print(f"[bold]Expires:[/bold] {group.end_date.strftime('%Y-%m-%d %H:%M UTC')}")
    console.print(f"[bold]Tags:[/bold] {', '.join(group.tags[:5])}\n")
    
    # Create table of all markets
    table = Table(title=f"All Markets in Event", show_header=True, header_style="bold cyan")
    table.add_column("Rank", style="dim", width=5)
    table.add_column("Candidate/Option", style="white", width=40)
    table.add_column("Odds", style="yellow", width=10, justify="right")
    table.add_column("Liquidity", style="green", width=12, justify="right")
    
    # Sort markets by odds (highest first)
    sorted_markets = sorted(
        group.markets,
        key=lambda m: max(o.price for o in m.outcomes) if m.outcomes else 0,
        reverse=True
    )
    
    # Show top 20 or all
    markets_to_show = sorted_markets if show_all else sorted_markets[:20]
    
    for i, market in enumerate(markets_to_show, 1):
        # Extract candidate/option name
        candidate = market.question.split("Will ")[-1].split(" win")[0] if "Will " in market.question else market.question
        if len(candidate) > 37:
            candidate = candidate[:34] + "..."
        
        # Get Yes probability (winning odds)
        yes_odds = next((o.price for o in market.outcomes if o.outcome.lower() in ('yes', 'y')), 0.0)
        
        # Format liquidity
        if market.liquidity >= 1_000_000:
            liq_str = f"${market.liquidity/1_000_000:.2f}M"
        elif market.liquidity >= 1_000:
            liq_str = f"${market.liquidity/1_000:.1f}k"
        else:
            liq_str = f"${market.liquidity:.0f}"
        
        table.add_row(
            str(i),
            candidate,
            f"{yes_odds:.1%}",
            liq_str
        )
    
    console.print(table)
    
    if not show_all and len(group.markets) > 20:
        console.print(f"\n[dim]Showing top 20 of {len(group.markets)} markets[/dim]")
        console.print(f"[dim]Note: Full list view coming soon[/dim]")

