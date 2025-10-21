"""Help command handler for Polly CLI."""

from rich.console import Console
from rich.panel import Panel

console = Console()

HELP_TEXT = """
[bold cyan]Available Commands:[/bold cyan]

  [yellow]/polls [days] [search][/yellow]    Browse polls (optional filters)
  [yellow]/research <poll_id>[/yellow]       Run deep research on a poll
  [yellow]/history [status][/yellow]         View research history (completed/pending/archived)
  [yellow]/portfolio[/yellow]                View trading performance
  [yellow]/help[/yellow]                     Show this help
  [yellow]/exit[/yellow]                     Quit Polly

[bold]Examples:[/bold]
  /polls                 Show all polls (sorted by expiry)
  /polls 7               Polls ending in 7 days
  /polls politics        Polls in "politics" category or mentioning it
  /polls bitcoin         Polls mentioning "bitcoin"
  /polls 7 bitcoin       Polls ending in 7 days mentioning "bitcoin"
  /polls 14 trump        Polls ending in 14 days mentioning "trump"
  /research 1            Run research on poll #1 from polls list
  /history completed     Show completed research
  /portfolio             View your paper trading stats
  
[dim]Search matches: question, category, description, and tags[/dim]
"""


def handle_help() -> None:
    """Display help information."""
    console.print(Panel(HELP_TEXT, title="Polly Help", border_style="green"))

