from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import DataTable, Static
from textual import on

from ..messages import TradeSelectedMsg


class DashboardView(Vertical):
    def compose(self):  # type: ignore[override]
        yield Static("Loading portfolio metrics...", id="metrics-summary")
        table = DataTable(id="trades-table", zebra_stripes=True)
        table.add_columns("ID", "Question", "Side", "Entry", "Current", "Unrealized", "Time Left")
        yield table

    @on(DataTable.RowSelected, "#trades-table")
    def _on_trade_row(self, event: DataTable.RowSelected) -> None:
        try:
            self.post_message(TradeSelectedMsg(int(event.row_key.value)))
        except Exception:
            pass

    def update_summary(self, summary_text: str) -> None:
        self.query_one("#metrics-summary", Static).update(summary_text)

    def update_active_trades(self, rows: list[tuple[str, ...]]) -> None:
        """Populate active trades table: (id, question, side, entry, current, unrealized, time_left, key)"""
        table = self.query_one("#trades-table", DataTable)
        table.clear()
        for row in rows:
            *cells, key = row
            table.add_row(*cells, key=key)


