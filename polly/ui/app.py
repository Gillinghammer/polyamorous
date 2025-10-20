from __future__ import annotations

from textual.app import App

from ..config import Config
from .screens.polls import PollsScreen


class PollyApp(App):
    """Main Polly TUI application (thin shell)."""

    TITLE = "Polly"
    SUB_TITLE = "Polymarket Research & Paper Trading"
    CSS_PATH = "styles.tcss"

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg

    def on_mount(self) -> None:
        self.push_screen(PollsScreen(self.cfg))


