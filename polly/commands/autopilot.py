"""Autopilot monitoring commands for Polly CLI."""

from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def handle_autopilot(args: str) -> None:
    """Handle /autopilot command.
    
    Subcommands:
        /autopilot status - Show service status
        /autopilot logs [lines] - Show recent logs
        /autopilot stats - Show statistics
    """
    parts = args.strip().split()
    subcommand = parts[0] if parts else "status"
    
    if subcommand == "status":
        _show_status()
    elif subcommand == "logs":
        lines = int(parts[1]) if len(parts) > 1 else 50
        _show_logs(lines)
    elif subcommand == "stats":
        _show_stats()
    else:
        console.print(f"[red]Unknown subcommand: {subcommand}[/red]")
        console.print("[yellow]Available: status, logs, stats[/yellow]")


def _show_status():
    """Show autopilot service status."""
    
    log_dir = Path.home() / ".polly" / "logs"
    autopilot_log = log_dir / "autopilot.log"
    
    if not autopilot_log.exists():
        console.print("[yellow]Autopilot service has never been run[/yellow]")
        console.print("\nTo start: [cyan]python -m polly.autopilot[/cyan]")
        console.print("Or in background: [cyan]nohup python -m polly.autopilot &[/cyan]")
        return
    
    # Check recent activity (last 5 minutes)
    try:
        # Read last line of log
        with open(autopilot_log, 'r') as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1]
                # Extract timestamp
                if " | " in last_line:
                    timestamp_str = last_line.split(" | ")[0]
                    try:
                        last_activity = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        time_since = (datetime.now() - last_activity).total_seconds()
                        
                        is_running = time_since < 300  # Active within last 5 minutes
                        
                        if is_running:
                            status_color = "green"
                            status_text = "RUNNING"
                        else:
                            status_color = "yellow"
                            status_text = f"STOPPED (last activity {int(time_since/60)} min ago)"
                    except:
                        status_color = "yellow"
                        status_text = "UNKNOWN"
                else:
                    status_color = "yellow"
                    status_text = "UNKNOWN"
            else:
                status_color = "yellow"
                status_text = "NO ACTIVITY"
    except Exception as e:
        console.print(f"[red]Error reading logs: {e}[/red]")
        return
    
    # Count recent cycles
    cycle_count = sum(1 for line in lines if "Cycle" in line and "started" in line)
    
    content = f"""
[bold {status_color}]Status: {status_text}[/bold {status_color}]

Log file: {autopilot_log}
Total cycles logged: {cycle_count}
Last activity: {timestamp_str if 'timestamp_str' in locals() else 'Unknown'}

[dim]To start service:[/dim]
  [cyan]python -m polly.autopilot[/cyan]
  
[dim]To view live logs:[/dim]
  [cyan]tail -f ~/.polly/logs/autopilot.log[/cyan]
    """
    
    console.print(Panel(content.strip(), title="Autopilot Service", border_style=status_color))


def _show_logs(lines: int = 50):
    """Show recent log entries."""
    
    log_file = Path.home() / ".polly" / "logs" / "autopilot.log"
    
    if not log_file.exists():
        console.print("[yellow]No log file found[/yellow]")
        return
    
    console.print(f"\n[cyan]Last {lines} log entries:[/cyan]\n")
    
    try:
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            recent = all_lines[-lines:]
            
            for line in recent:
                # Color code by level
                if "ERROR" in line:
                    console.print(f"[red]{line.rstrip()}[/red]")
                elif "WARNING" in line:
                    console.print(f"[yellow]{line.rstrip()}[/yellow]")
                elif "INFO" in line:
                    console.print(f"[dim]{line.rstrip()}[/dim]")
                else:
                    console.print(line.rstrip())
    except Exception as e:
        console.print(f"[red]Error reading logs: {e}[/red]")


def _show_stats():
    """Show autopilot statistics."""
    
    console.print("[cyan]Autopilot Statistics[/cyan]")
    console.print("[dim]Coming soon: cycle stats, trade counts, performance metrics[/dim]")

