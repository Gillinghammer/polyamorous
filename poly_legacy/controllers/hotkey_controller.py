"""Hotkey controller for centralized key binding handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import PolyApp


class HotkeyController:
    """Centralized hotkey handling for the Poly TUI."""
    
    def __init__(self, app: PolyApp) -> None:
        self._app = app
    
    def handle_sort_liquidity(self) -> None:
        """Sort polls by liquidity."""
        self._app._sort_key = "liquidity"
        self._app._render_polls_table()
    
    def handle_sort_time(self) -> None:
        """Sort polls by time remaining."""
        self._app._sort_key = "time"
        self._app._render_polls_table()
    
    def handle_sort_volume(self) -> None:
        """Sort polls by volume."""
        self._app._sort_key = "volume"
        self._app._render_polls_table()
    
    def handle_days_filter(self, days: int | None) -> None:
        """Apply day filter to polls."""
        self._app._day_filter = days
        self._app._render_polls_table()
    
    def handle_category_clear(self) -> None:
        """Clear category filter."""
        self._app._category_filter = None
        self._app._render_polls_table()
    
    def handle_toggle_researched(self) -> None:
        """Toggle researched filter."""
        self._app._filter_researched = not self._app._filter_researched
        self._app._render_polls_table()
    
    def handle_toggle_history_undecided(self) -> None:
        """Toggle history filter to undecided only."""
        self._app._research_history_filter = "undecided" if self._app._research_history_filter != "undecided" else "all"
        try:
            self._app._render_research_history(self._app._research_history_filter)
        except Exception:
            pass
    
    def handle_toggle_citations(self) -> None:
        """Toggle citations visibility."""
        try:
            md = self._app.query_one("#citations-list", Markdown)
            md.display = not md.display
            self._app.refresh(layout=True)
        except Exception:
            pass
    
    def handle_toggle_logs(self) -> None:
        """Toggle research logs visibility."""
        try:
            md = self._app.query_one("#research-log", Markdown)
            md.display = not md.display
        except Exception:
            pass
    
    def handle_toggle_edge_help(self) -> None:
        """Toggle edge help visibility."""
        try:
            help_ = self._app.query_one("#edge-help", Static)
            help_.display = not help_.display
        except Exception:
            pass
