"""Command line entry point for launching the Poly TUI."""

from __future__ import annotations

from .app import PolyApp


def main() -> None:
    """Launch the Poly Textual app."""

    PolyApp().run()


if __name__ == "__main__":
    main()
