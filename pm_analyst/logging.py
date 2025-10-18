from __future__ import annotations

import logging
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


def configure_logging(level: int = logging.INFO, console: Optional[Console] = None) -> None:
    """Configure structured logging with Rich handler."""

    console = console or Console()
    handler = RichHandler(console=console, rich_tracebacks=True, markup=True)
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
        force=True,
    )


__all__ = ["configure_logging"]
