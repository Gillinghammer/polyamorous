"""ASCII banner and welcome message for Polly CLI."""

BANNER = """
╔═══════════════════════════════════════════════╗
║   ██████╗  ██████╗ ██╗     ██╗  ██╗   ██╗    ║
║   ██╔══██╗██╔═══██╗██║     ██║  ╚██╗ ██╔╝    ║
║   ██████╔╝██║   ██║██║     ██║   ╚████╔╝     ║
║   ██╔═══╝ ██║   ██║██║     ██║    ╚██╔╝      ║
║   ██║     ╚██████╔╝███████╗███████╗██║       ║
║   ╚═╝      ╚═════╝ ╚══════╝╚══════╝╚═╝       ║
║                                               ║
║   Polymarket Research & Paper Trading         ║
╚═══════════════════════════════════════════════╝

Welcome! Type /help to see available commands.
"""


def display_banner() -> None:
    """Display the Polly banner."""
    print(BANNER)

