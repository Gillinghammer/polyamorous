from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static
from textual.containers import Grid

from ...db import Database
from ...config import Config
from ...services.portfolio import PortfolioService


class DashboardScreen(Screen):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.db = Database(cfg.db_path)
        self.portfolio = PortfolioService(self.db)

    def compose(self) -> ComposeResult:
        yield Header()
        grid = Grid()
        grid.styles.grid_size_rows = 2
        grid.styles.grid_size_columns = 2
        grid.styles.grid_gutter = 1
        m = self.portfolio.compute_metrics()
        yield grid
        grid.mount(Static(f"Available\n${m.available_cash:,.2f}"))
        grid.mount(Static(f"Unrealized\n${m.unrealized_pnl:,.2f}"))
        grid.mount(Static(f"Realized\n${m.realized_pnl:,.2f}"))
        grid.mount(Static("Win Rate\n—"))
        yield Footer()


