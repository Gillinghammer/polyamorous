"""Command line entry point for launching the Poly TUI."""

from __future__ import annotations

from dotenv import load_dotenv
from .app import PolyApp


def main() -> None:
    """Launch the Poly Textual app."""
    # Load environment variables from a local .env file if present
    load_dotenv()
    PolyApp().run()


if __name__ == "__main__":
    main()
