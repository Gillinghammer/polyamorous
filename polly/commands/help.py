"""Help command handler for Polly CLI."""

from rich.console import Console
from rich.panel import Panel

console = Console()

HELP_TEXT = """
[bold cyan]Available Commands:[/bold cyan]

  [yellow]/polls [days] [search] [flags][/yellow]  Browse polls with filters
  [yellow]/research <poll_id>[/yellow]             Run deep research on a poll
  [yellow]/history [status][/yellow]               View research history (completed/pending/archived)
  [yellow]/portfolio[/yellow]                      View trading performance
  [yellow]/trade <market> <outcome> [amt][/yellow] Manually execute trade (real mode only)
  [yellow]/close <trade_id>[/yellow]               Close active position (real mode only)
  [yellow]/help[/yellow]                           Show this help
  [yellow]/exit[/yellow]                           Quit Polly

[bold cyan]Market Types:[/bold cyan]
  [green]Binary Markets[/green]     Simple Yes/No predictions (e.g., "Will Bitcoin reach $130k?")
  [green]⬐ Grouped Events[/green]    Multi-outcome predictions (e.g., "2028 Presidential Nominee")
                      - Shows number of options (e.g., "128 opts")
                      - Displays top candidates with their odds
                      - Research can recommend multiple positions for hedging

[bold cyan]Polls Filters:[/bold cyan]
  [green][days][/green]              Filter by days until expiry (7, 14, 30, or 180)
  [green][search][/green]            Search in question, category, description, tags
  [green]-odds <max>[/green]         Show only markets with max odds ≤ value (1-99)
  [green]-asc <column>[/green]       Sort ascending by: category, question, odds, expires, liquidity
  [green]-dsc <column>[/green]       Sort descending by: category, question, odds, expires, liquidity

[bold]Examples:[/bold]
  /polls                      All polls (binary + grouped events)
  /polls 7                    Items ending in 7 days
  /polls election             Search for "election" markets
  /polls 2028                 Search for "2028" events
  /polls -odds 60             Competitive markets with max odds ≤ 60%
  /polls -dsc liquidity       All polls sorted by liquidity (highest first)
  /research 1                 Research poll #1 (works for both types)
  /research 2                 Research grouped event (analyzes all candidates)
  /history completed          Show completed research
  /portfolio                  View positions (grouped events shown together)
  /trade 5 Yes 100            Trade $100 on "Yes" for binary market #5
  /close 12                   Close trade #12 (real mode)

[bold cyan]Multi-Outcome Events:[/bold cyan]
  • Grouped events (marked with ⬐) contain multiple related markets
  • Example: "2028 Presidential Nominee" has 128 candidate markets
  • Research analyzes ALL candidates and can recommend multiple positions
  • Portfolio groups related positions for easy tracking
  • Ideal for hedge strategies and complex predictions
  
[dim]Note: Markets with any outcome ≥80% odds or liquidity <$50k are auto-filtered[/dim]
[dim]Trading mode set in config: mode: paper or mode: real[/dim]
"""


def handle_help() -> None:
    """Display help information."""
    console.print(Panel(HELP_TEXT, title="Polly Help", border_style="green"))

