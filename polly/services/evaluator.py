"""Position evaluation logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from polly.config import ResearchConfig
from polly.models import Market, MarketGroup, MarketRecommendation, ResearchResult

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
    
    def validate_longshot(self, rec: MarketRecommendation, current_odds: float) -> tuple[bool, str]:
        """Check if longshot position has genuine substance beyond pure mathematical edge.
        
        For extreme longshots (<5% market odds), requires:
        - Confidence ≥ 50% (not purely speculative)
        - Assessed probability ≥ 5% (believe it's actually viable)
        - Rationale mentions concrete catalysts (polls, trends, events)
        
        Args:
            rec: The recommendation to validate
            current_odds: Current market odds for this position
            
        Returns:
            (is_valid, reason) tuple
        """
        
        # If not a longshot, approve automatically
        if current_odds >= 0.05:  # ≥5% is not extreme longshot
            return (True, "Not a longshot")
        
        # For extreme longshots (<5%), apply higher standards
        
        # Check 1: Confidence must be ≥50% (not just 35%)
        if rec.confidence < 50:
            return (False, f"Longshot confidence too low ({rec.confidence:.0f}% < 50%)")
        
        # Check 2: Must believe it's at least 5% likely
        if rec.probability < 0.05:
            return (False, f"Assessed probability too low ({rec.probability:.1%} < 5%)")
        
        # Check 3: Rationale must mention concrete reasons
        rationale_lower = rec.rationale.lower()
        
        # Look for evidence of substance
        substance_keywords = [
            'poll', 'polling', 'survey',  # Data
            'surge', 'rising', 'momentum', 'trend', 'gaining',  # Movement
            'endorsement', 'support', 'backed',  # Catalysts  
            'scandal', 'controversy',  # Events affecting others
            'recent', 'latest', 'yesterday', 'this week',  # Timely info
            'percent', '%',  # Actual numbers
        ]
        
        has_substance = any(word in rationale_lower for word in substance_keywords)
        
        if not has_substance:
            return (False, "No concrete catalyst found (pure math edge)")
        
        # Passed all checks
        return (True, f"Has substance (conf: {rec.confidence:.0f}%, prob: {rec.probability:.1%})")
    
    def evaluate_group_recommendations(
        self,
        recommendations: list[MarketRecommendation],
        group: MarketGroup,
    ) -> list[dict]:
        """Evaluate multiple position recommendations across a grouped event.
        
        Respects varying position sizes suggested by research for portfolio optimization.
        
        Returns:
            List of position evaluations with entry suggestions and combined metrics.
        """
        evaluations = []
        total_ev = 0.0
        total_stake = 0.0
        suggested_count = 0
        
        for rec in recommendations:
            # Find the corresponding market in the group
            market = next((m for m in group.markets if m.id == rec.market_id), None)
            if not market:
                continue
            
            # Get current market odds (Yes probability for winning)
            current_price = 0.0
            for outcome in market.outcomes:
                if outcome.outcome.lower() in ('yes', 'y'):
                    current_price = outcome.price
                    break
            
            if current_price == 0.0:
                current_price = 0.5  # Fallback
            
            # Calculate edge
            edge = rec.probability - current_price
            
            # Calculate expected value using SUGGESTED stake amount
            stake = rec.suggested_stake
            if current_price > 0:
                shares = stake / current_price
                win_value = shares * 1.0  # Binary contracts pay $1 per share
                expected_value = (rec.probability * win_value) - ((1 - rec.probability) * stake)
            else:
                expected_value = 0.0
            
            # Determine if entry is suggested
            meets_edge = abs(edge) >= self._config.min_edge_threshold
            meets_confidence = rec.confidence >= self._config.min_confidence_threshold
            has_positive_ev = expected_value > 0
            
            # For portfolio strategies, be more flexible:
            # - Respect research's entry_suggested flag (research understands portfolio context)
            # - But still require positive EV at minimum
            # - Allow lower confidence for hedge positions if they have large edge
            is_hedge_position = edge > (self._config.min_edge_threshold * 2)  # 2x normal edge threshold
            
            # Entry logic:
            # 1. If research suggests AND has positive EV AND meets normal thresholds → enter
            # 2. If research suggests AND has positive EV AND is hedge (2x edge) → enter even if lower confidence
            # 3. Otherwise → skip
            
            if rec.entry_suggested and has_positive_ev:
                if meets_edge and meets_confidence:
                    entry_suggested = True  # Standard entry
                elif is_hedge_position and rec.confidence >= (self._config.min_confidence_threshold * 0.5):
                    entry_suggested = True  # Hedge entry (relaxed confidence if huge edge)
                else:
                    entry_suggested = False  # Doesn't meet minimum standards
            else:
                entry_suggested = False
            
            if entry_suggested:
                suggested_count += 1
                total_ev += expected_value
                total_stake += stake
            
            evaluations.append({
                "market_id": rec.market_id,
                "market_question": rec.market_question,
                "prediction": rec.prediction,
                "probability": rec.probability,
                "confidence": rec.confidence,
                "current_odds": current_price,
                "edge": edge,
                "expected_value": expected_value,
                "suggested_stake": stake,
                "entry_suggested": entry_suggested,
                "rationale": rec.rationale,
                "meets_edge": meets_edge,
                "meets_confidence": meets_confidence,
            })
        
        # Add combined metrics to each evaluation
        for eval_dict in evaluations:
            eval_dict["combined_ev"] = total_ev
            eval_dict["total_stake"] = total_stake
            eval_dict["suggested_count"] = suggested_count
            eval_dict["portfolio_pct"] = (eval_dict["suggested_stake"] / total_stake * 100) if total_stake > 0 else 0
        
        return evaluations
