"""Main CLI interface for Polly."""

import os
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console

from polly.config import load_config, DEFAULT_CONFIG_PATH, AppConfig
from polly.models import Market
from polly.services.evaluator import PositionEvaluator
from polly.services.polymarket import PolymarketService
from polly.services.research import ResearchService
from polly.storage.research import ResearchRepository
from polly.storage.trades import TradeRepository
from polly.ui.banner import display_banner

# Import command handlers
from polly.commands.help import handle_help
from polly.commands.polls import handle_polls
from polly.commands.portfolio import handle_portfolio
from polly.commands.history import handle_history
from polly.commands.research import handle_research

console = Console()

# Load environment variables
load_dotenv()

# History file path
HISTORY_FILE = Path.home() / ".polly" / "history.txt"


class CommandContext:
    """Holds all services and state for command handlers."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.polymarket = PolymarketService(config.polls)
        self.research_service = ResearchService(config.research)
        self.evaluator = PositionEvaluator(config.research)
        self.trade_repo = TradeRepository(config.database_path)
        self.research_repo = ResearchRepository(config.database_path)
        self.markets_cache: List[Market] = []


def check_api_key() -> bool:
    """Check if XAI_API_KEY is set."""
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        console.print("[red]Error: XAI_API_KEY environment variable not set.[/red]")
        console.print("[yellow]Please set your xAI API key in a .env file or environment:[/yellow]")
        console.print("  export XAI_API_KEY='your_api_key_here'")
        console.print("\nOr create a .env file with:")
        console.print("  XAI_API_KEY=your_api_key_here")
        return False
    return True


def ensure_config() -> None:
    """Ensure default config directory and file exist."""
    config_dir = DEFAULT_CONFIG_PATH.parent
    config_dir.mkdir(parents=True, exist_ok=True)
    
    if not DEFAULT_CONFIG_PATH.exists():
        console.print(f"[yellow]Creating default config at {DEFAULT_CONFIG_PATH}[/yellow]")
        
        default_config = """# Polly Configuration

research:
  min_confidence_threshold: 70
  min_edge_threshold: 0.10
  model_name: "grok-4-fast"
  default_rounds: 20
  enable_code_execution: false
  topic_count_min: 10
  topic_count_max: 20

paper_trading:
  default_stake: 100
  starting_cash: 10000

polls:
  top_n: 20
  exclude_categories:
    - sports
    - esports

database:
  path: ~/.polly/trades.db
"""
        DEFAULT_CONFIG_PATH.write_text(default_config)


def route_command(command: str, context: CommandContext) -> None:
    """Route command to appropriate handler.
    
    Args:
        command: User input command string
        context: Command context with services
    """
    command = command.strip()
    
    if not command:
        return
    
    # Parse command and arguments
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    
    # Route to handlers
    if cmd == "/help":
        handle_help()
    
    elif cmd == "/polls":
        context.markets_cache = handle_polls(args, context.polymarket)
    
    elif cmd == "/research":
        handle_research(
            args=args,
            markets_cache=context.markets_cache,
            polymarket=context.polymarket,
            research_service=context.research_service,
            evaluator=context.evaluator,
            research_repo=context.research_repo,
            trade_repo=context.trade_repo,
            research_config=context.config.research,
            paper_config=context.config.paper_trading,
        )
    
    elif cmd == "/portfolio":
        handle_portfolio(context.trade_repo, context.config.paper_trading)
    
    elif cmd == "/history":
        handle_history(args, context.research_repo, context.polymarket)
    
    elif cmd == "/exit":
        console.print("[yellow]Goodbye![/yellow]")
        sys.exit(0)
    
    else:
        console.print(f"[red]Unknown command: {cmd}[/red]")
        console.print("[dim]Type /help to see available commands[/dim]")


def main() -> None:
    """Main entry point for Polly CLI."""
    
    # Display banner
    display_banner()
    
    # Check API key
    if not check_api_key():
        sys.exit(1)
    
    # Ensure config exists
    ensure_config()
    
    # Load config
    try:
        config = load_config()
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        sys.exit(1)
    
    # Initialize context
    try:
        context = CommandContext(config)
    except Exception as e:
        console.print(f"[red]Error initializing services: {e}[/red]")
        sys.exit(1)
    
    # Ensure history file directory exists
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Create prompt session with history
    session = PromptSession(
        history=FileHistory(str(HISTORY_FILE)),
        enable_history_search=True,
    )
    
    # Main command loop
    while True:
        try:
            # Use prompt_toolkit for input with history support
            command = session.prompt("\npolly> ").strip()
            if command:
                route_command(command, context)
        except KeyboardInterrupt:
            console.print("\n[yellow]Goodbye![/yellow]")
            break
        except EOFError:
            console.print("\n[yellow]Goodbye![/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            # In production, you might want to log full traceback
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")


if __name__ == "__main__":
    main()

