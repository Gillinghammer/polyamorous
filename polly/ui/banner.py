"""ASCII banner and welcome message for Polly CLI."""

from rich.console import Console

console = Console()

BANNER = """[yellow]╔═══════════════════════════════════════════════╗
║    ██████╗  ██████╗ ██╗     ██╗  ██╗   ██╗    ║
║    ██╔══██╗██╔═══██╗██║     ██║  ╚██╗ ██╔╝    ║
║    ██████╔╝██║   ██║██║     ██║   ╚████╔╝     ║
║    ██╔═══╝ ██║   ██║██║     ██║    ╚██╔╝      ║
║    ██║     ╚██████╔╝███████╗███████╗██║       ║
║    ╚═╝      ╚═════╝ ╚══════╝╚══════╝╚═╝       ║
║                                               ║
║           Polymarket Deep Research            ║
╚═══════════════════════════════════════════════╝[/yellow]

[dim]Welcome! Type [bold]/help[/bold] to see available commands.[/dim]"""


def display_banner() -> None:
    """Display the Polly banner."""
    console.print(BANNER)

