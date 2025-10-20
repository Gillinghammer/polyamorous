"""Command-line interface for Polly.

Commands:
- init: initialize the SQLite database and settings
- ingest: fetch markets/outcomes from official Polymarket REST
- run: launch the Textual TUI
- agent-run: run the autonomous agent flow (if enabled)
- resolve: resolve closed markets and close trades
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from .config import Config
from .logging import configure_logging
from .db import Database
from .services.polymarket import IngestionService
from .services.portfolio import PortfolioService
from .services.trading_paper import PaperTradingGateway
from .services.resolution import ResolutionService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="polly", description="Polly - Polymarket TUI")

    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize the database and settings")
    p_init.add_argument("--starting-balance", type=float, required=True, help="Starting balance in USDC")

    p_ingest = sub.add_parser("ingest", help="Fetch markets and outcomes")
    p_ingest.add_argument("--open-only", action="store_true", help="Only ingest open/active markets")
    p_ingest.add_argument("--since", type=int, default=None, help="Only markets updated within HOURS")

    sub.add_parser("run", help="Launch the TUI")

    sub.add_parser("agent-run", help="Run agent mode once if enabled")

    sub.add_parser("resolve", help="Resolve closed markets and close trades")

    p_settings = sub.add_parser("settings", help="View or update settings")
    g = p_settings.add_mutually_exclusive_group()
    g.add_argument("--agent-enabled", choices=["0", "1", "true", "false"], help="Enable(1/true) or disable(0/false) agent")
    p_settings.add_argument("--agent-window-days", type=int, help="Agent window in days (1-7)")

    return parser


def cmd_init(cfg: Config, db: Database, starting_balance: float) -> int:
    db.init_schema()
    db.set_setting("starting_balance_usdc", str(starting_balance))
    print(f"Database initialized at {cfg.db_path} with starting balance ${starting_balance:,.2f}")
    return 0


def cmd_ingest(cfg: Config, db: Database, open_only: bool, since_hours: Optional[int]) -> int:
    ingestion = IngestionService(cfg, db)
    count = ingestion.ingest_markets(open_only=open_only, since_hours=since_hours)
    print(f"Ingested {count} markets")
    return 0


def cmd_run(cfg: Config) -> int:
    # Lazy import to avoid Textual dependency at CLI import time
    from .ui.app import PollyApp

    # Suppress stderr logs during TUI to prevent overlay; still log to file
    configure_logging(debug=False, to_stderr=False)
    app = PollyApp(cfg)
    app.run()
    return 0


def cmd_agent_run(cfg: Config, db: Database) -> int:
    # Minimal stub: perform selection and attempt entries via paper trading
    portfolio = PortfolioService(db)
    trading = PaperTradingGateway(db)
    ingestion = IngestionService(cfg, db)

    # Respect agent toggle
    enabled = (db.get_setting("agent_enabled", "0") or "0").lower() in {"1", "true", "yes"}
    if not enabled:
        print("Agent mode is disabled. Enable by setting settings.agent_enabled=1.")
        return 0

    # Ensure markets are reasonably fresh
    ingestion.ingest_markets(open_only=True, since_hours=24)

    # Delegate to portfolio to select eligible polls and enter
    decisions = portfolio.run_agent_once(trading_gateway=trading, window_days=portfolio.get_agent_window_days())
    print(f"Agent processed {decisions.processed} polls, entered {decisions.entered}, skipped {decisions.skipped}")
    return 0


def cmd_resolve(cfg: Config, db: Database) -> int:
    resolver = ResolutionService(cfg, db)
    closed = resolver.resolve_all()
    print(f"Resolved {closed} trades")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv or sys.argv[1:]
    parser = _build_parser()
    args = parser.parse_args(argv)

    cfg = Config.load()
    # Avoid stderr logs for TUI; keep for CLI subcommands
    if args.command == "run":
        configure_logging(debug=args.debug, to_stderr=False)
    else:
        configure_logging(debug=args.debug, to_stderr=True)
    db = Database(cfg.db_path)

    if args.command == "init":
        return cmd_init(cfg, db, starting_balance=args.starting_balance)
    if args.command == "ingest":
        return cmd_ingest(cfg, db, open_only=args.open_only, since_hours=args.since)
    if args.command == "run":
        return cmd_run(cfg)
    if args.command == "agent-run":
        return cmd_agent_run(cfg, db)
    if args.command == "resolve":
        return cmd_resolve(cfg, db)
    if args.command == "settings":
        # View current if no args; otherwise update
        updated = False
        if args.agent_enabled is not None:
            val = "1" if args.agent_enabled in {"1", "true"} else "0"
            db.set_setting("agent_enabled", val)
            updated = True
        if args.agent_window_days is not None:
            db.set_setting("agent_window_days", str(max(1, min(7, args.agent_window_days))))
            updated = True
        if not updated:
            print("Current settings:")
            print("  agent_enabled=", db.get_setting("agent_enabled", "0"))
            print("  agent_window_days=", db.get_setting("agent_window_days", "3"))
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


