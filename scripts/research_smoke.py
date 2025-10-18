#!/usr/bin/env python3
"""Quick smoke test for Grok research integration.

Usage:
  python scripts/research_smoke.py --question "Sundar Pichai out as Google CEO in 2025?"
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from poly.config import ResearchConfig
from poly.models import Market, MarketOutcome
from poly.services.research import ResearchService


def build_market(question: str) -> Market:
    """Build a minimal Market entity for ad-hoc research tests."""

    return Market(
        id="smoke-test-1",
        question=question,
        description="",
        category="AdHoc",
        liquidity=0.0,
        volume_24h=0.0,
        end_date=datetime.now(tz=timezone.utc) + timedelta(days=60),
        outcomes=[
            MarketOutcome(token_id="yes", outcome="Yes", price=0.11),
            MarketOutcome(token_id="no", outcome="No", price=0.89),
        ],
    )


async def run(question: str) -> None:
    load_dotenv()
    service = ResearchService(ResearchConfig())
    market = build_market(question)

    def on_progress(p):
        print(f"[Progress] {p.round_number}/{p.total_rounds}: {p.message}")

    result = await service.conduct_research(market, on_progress, rounds=6)

    print("\n=== RESULT ===")
    print("Prediction:", result.prediction)
    print("Probability:", f"{result.probability:.2f}")
    print("Confidence:", f"{result.confidence:.1f}")
    print("Rationale:", result.rationale[:600])
    print("Key Findings (up to 10):")
    for item in result.key_findings[:10]:
        print(" -", item)
    print("Citations:", len(result.citations))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.question))


if __name__ == "__main__":
    main()


