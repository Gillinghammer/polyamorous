from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..services.calculations import EdgeReport
from ..services.polymarket import MarketData

NEON_ACCENT = "#00e5ff"


def _format_time(resolves_at: datetime) -> str:
    delta = resolves_at - datetime.now(timezone.utc)
    hours = max(delta.total_seconds() / 3600, 0)
    if hours < 24:
        return f"T-{hours:.0f}h"
    days = hours / 24
    return f"T-{days:.0f}d"


def render_markets(markets: Iterable[MarketData]) -> Table:
    table = Table(title="Filtered Markets", show_lines=False, expand=True, box=None)
    table.add_column("Slug", style="bold")
    table.add_column("Time", style=NEON_ACCENT)
    table.add_column("YES", justify="right")
    table.add_column("NO", justify="right")
    table.add_column("24h Vol", justify="right")
    table.add_column("Open Interest", justify="right")
    table.add_column("Depth", justify="right")
    for market in markets:
        table.add_row(
            market.slug,
            _format_time(market.resolves_at),
            f"{market.prices['yes']:.2f}",
            f"{market.prices['no']:.2f}",
            f"${market.volume_24h:,.0f}",
            f"${market.open_interest:,.0f}",
            f"${market.top_of_book_depth:,.0f}",
        )
    return table


def render_research_panel(market: MarketData, edge: EdgeReport, rationale: str, citations: List[str], confidence: float) -> Panel:
    body = Text(justify="left")
    body.append(f"EV Side: {edge.side.upper()}\n", style=NEON_ACCENT)
    body.append(f"Edge: {edge.edge:+.2%}\n")
    body.append(f"ROI: {edge.roi:+.2%}\n")
    body.append(f"APR: {edge.apr:+.2f}\n")
    body.append(f"Confidence: {confidence:.0%}\n\n")
    body.append(rationale)
    if citations:
        body.append("\n\nCitations:\n", style="bold")
        for idx, citation in enumerate(citations, start=1):
            body.append(f"[{idx}] {citation}\n", style="dim")
    return Panel(body, title=market.question, border_style=NEON_ACCENT)


def render_layout(markets: Iterable[MarketData], selected: Optional[MarketData], edge: Optional[EdgeReport], rationale: str, citations: List[str], confidence: float) -> Panel:
    table = render_markets(markets)
    if selected and edge:
        detail = render_research_panel(selected, edge, rationale, citations, confidence)
    else:
        detail = Panel("Select a market to view research", border_style=NEON_ACCENT)
    columns = Table.grid(expand=True)
    columns.add_column(ratio=1)
    columns.add_column(ratio=1)
    columns.add_row(table, detail)
    footer = Text("[A] Accept  [R] Reject  [D] Details  [C] Citations  [H] History  [S] Settings", style=NEON_ACCENT)
    layout = Table.grid(expand=True)
    layout.add_row(columns)
    layout.add_row(Align.center(footer))
    return Panel(layout, border_style="#003f5c")


def display_scan(console: Console, markets: Iterable[MarketData]) -> None:
    console.print(render_layout(markets, None, None, "", [], 0.0))


def display_review(console: Console, markets: Iterable[MarketData], selected: MarketData, edge: EdgeReport, rationale: str, citations: List[str], confidence: float) -> None:
    console.print(render_layout(markets, selected, edge, rationale, citations, confidence))


__all__ = ["display_scan", "display_review"]
