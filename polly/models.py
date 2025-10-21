"""Domain models for the Polly application."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional


@dataclass(slots=True)
class MarketOutcome:
    """Represents a tradeable outcome within a market."""

    token_id: str
    outcome: str
    price: float
    winner: bool | None = None


@dataclass(slots=True)
class Market:
    """Polymarket market metadata used by the UI."""

    id: str
    question: str
    description: str
    category: str
    liquidity: float
    volume_24h: float
    end_date: datetime
    outcomes: List[MarketOutcome]
    tags: List[str] = field(default_factory=list)

    @property
    def time_remaining(self) -> timedelta:
        """Return the remaining time until resolution."""

        return max(self.end_date - datetime.now(tz=self.end_date.tzinfo), timedelta())

    def formatted_odds(self) -> Dict[str, float]:
        """Return a mapping of outcome label to current price."""

        return {outcome.outcome: outcome.price for outcome in self.outcomes}


@dataclass(slots=True)
class ResearchProgress:
    """Represents incremental progress during a research run."""

    message: str
    round_number: int
    total_rounds: int
    completed: bool = False


@dataclass(slots=True)
class ResearchResult:
    """Final research artefact returned by the Grok workflow."""

    market_id: str
    prediction: str
    probability: float
    confidence: float
    rationale: str
    key_findings: List[str]
    citations: List[str]
    rounds_completed: int
    created_at: datetime
    duration_minutes: int
    # Usage and cost estimation
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    estimated_cost_usd: float | None = None


@dataclass(slots=True)
class Trade:
    """Paper or real trade stored in SQLite."""

    id: int | None
    market_id: str
    question: str
    category: str | None
    selected_option: str
    entry_odds: float
    stake_amount: float
    entry_timestamp: datetime
    predicted_probability: float
    confidence: float
    research_id: int | None
    status: str
    resolves_at: datetime
    actual_outcome: Optional[str]
    profit_loss: Optional[float]
    closed_at: Optional[datetime]
    trade_mode: str = "paper"  # "paper" or "real"
    order_id: Optional[str] = None  # Polymarket order ID for real trades


@dataclass(slots=True)
class PortfolioMetrics:
    """Aggregated dashboard metrics."""

    active_positions: int
    win_rate: float
    total_profit: float
    average_profit: float
    projected_apr: float
    recent_trades: List[Trade]
    # Aggregate research spend for the session/app lifetime (not persisted yet)
    research_spend_usd: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    best_category: Optional[str] = None
    worst_category: Optional[str] = None
    profit_by_category: Dict[str, float] = field(default_factory=dict)
    cash_available: float = 0.0
    cash_in_play: float = 0.0

