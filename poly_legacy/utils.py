"""Utility functions for the Poly TUI application."""

from __future__ import annotations


def format_timedelta(delta) -> str:
    """Pretty print time remaining."""
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def build_citations_md(citations: list[str] | None) -> tuple[int, int, str]:
    """Build citations markdown and count web vs X posts."""
    from urllib.parse import urlparse
    
    web_count = 0
    x_count = 0
    parts: list[str] = []
    
    for url in (citations or []):
        try:
            netloc = urlparse(url).netloc.lower()
        except Exception:
            netloc = ""
        is_x = ("x.com" in netloc) or ("twitter.com" in netloc) or (netloc == "t.co")
        if is_x:
            x_count += 1
        elif netloc:
            web_count += 1
        label = netloc or url
        parts.append(f"- {label} — {url}")
    
    return web_count, x_count, "\n".join(parts)
