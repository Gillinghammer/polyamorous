"""Position evaluation logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..config import ResearchConfig
from ..models import Market, ResearchResult

Recommendation = Literal["enter", "pass"]


@dataclass(slots=True)
class Evaluation:
    """Structured evaluation output."""

    edge: float
    recommendation: Recommendation
    rationale: str


class PositionEvaluator:
    """Applies configuration thresholds to research output."""

    def __init__(self, config: ResearchConfig) -> None:
        self._config = config

    def evaluate(self, market: Market, research: ResearchResult) -> Evaluation:
        """Return an evaluation for the researched market."""

        market_odds = market.formatted_odds()
        predicted_price = research.probability

        reference_price = market_odds.get(research.prediction)
        if reference_price is None:
            reference_price = sum(market_odds.values()) / max(len(market_odds), 1)

        edge = predicted_price - reference_price
        meets_edge = abs(edge) >= self._config.min_edge_threshold
        meets_confidence = research.confidence >= self._config.min_confidence_threshold

        if meets_edge and meets_confidence:
            recommendation: Recommendation = "enter"
            rationale = (
                "Research shows sufficient edge over market odds with confidence above threshold."
            )
        else:
            recommendation = "pass"
            rationale = "Edge or confidence threshold not met; passing to protect accuracy."

        return Evaluation(edge=edge, recommendation=recommendation, rationale=rationale)
