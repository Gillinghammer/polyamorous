from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, LoadingIndicator, Button
from textual.containers import Vertical


class ResearchProgress(ModalScreen[None]):
    """Simple modal to show research progress."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Research in progress…", id="rp-title")
            yield LoadingIndicator(id="rp-loading")
            yield Static("Starting…", id="rp-status")
            yield Button("Cancel", id="rp-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rp-cancel":
            # Let caller decide; we simply dismiss
            self.dismiss(None)

    def update_status(self, text: str) -> None:
        self.query_one("#rp-status", Static).update(text)


