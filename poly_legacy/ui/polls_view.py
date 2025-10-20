from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import DataTable, Static
from textual import on

from ..messages import PollSelectedMsg


class PollsView(Vertical):
    def compose(self):  # type: ignore[override]
        table = DataTable(id="polls-table", zebra_stripes=True)
        table.add_columns(
            "Question",
            "Options",
            "Current Odds",
            "Time Left",
            "Volume 24h",
            "Research",
            "Rec",
            "Trade",
        )
        yield table
        yield Static("Select a poll and press Enter to start research. Select again to open details.", id="polls-hint")

    @on(DataTable.RowSelected, "#polls-table")
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        self.post_message(PollSelectedMsg(str(event.row_key.value)))

    def update_rows(self, rows: list[tuple[str, ...]]):
        """Clear and populate the polls table. Each row tuple should end with key as last element.

        rows: list of tuples (question, options, odds, time_left, volume, research_cell, rec_cell, trade_cell, key)
        """
        table = self.query_one("#polls-table", DataTable)
        table.clear()
        for row in rows:
            *cells, key = row
            table.add_row(*cells, key=key)


