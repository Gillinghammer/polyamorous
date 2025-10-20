from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.containers import Horizontal
from textual.widgets import Static, Switch


class FiltersBar(Widget):
    """Top filters row with view indicator and open-only switch."""

    DEFAULT_CSS = """
    FiltersBar {
        height: 3;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("View: Inbox (i/r/e/a/c)", id="filter-view-indicator")
            yield Switch(value=True, id="filter-open-only")


