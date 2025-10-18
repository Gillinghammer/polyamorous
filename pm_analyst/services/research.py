from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import datetime
from typing import List

from ..config import Settings


@dataclass
class ResearchResult:
    probability_yes: float
    confidence: float
    rationale: str
    citations: List[str]
    rounds: int


class ResearchOrchestrator:
    """Stub Grok orchestrator producing deterministic pseudo-research."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def run_research(self, market_id: str, question: str) -> ResearchResult:
        seed = int(hashlib.sha256(market_id.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(seed)
        probability_yes = round(rng.uniform(0.35, 0.75), 2)
        confidence = round(rng.uniform(0.55, 0.9), 2)
        rounds = rng.randint(2, self.settings.research.max_rounds)
        rationale = (
            f"Automated summary for '{question}'. Synthesized sentiment, polling, and expert commentary suggest the modeled "
            f"probability of YES is {probability_yes:.2f}."
        )
        citations = [
            "https://news.example.com/article",
            "https://x.com/thread",
            "https://analysis.example.com/report",
        ][: rounds]
        return ResearchResult(
            probability_yes=probability_yes,
            confidence=confidence,
            rationale=rationale,
            citations=citations,
            rounds=rounds,
        )


__all__ = ["ResearchOrchestrator", "ResearchResult"]
