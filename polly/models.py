from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal


Recommendation = Literal["enter", "pass"]
CitationKind = Literal["web", "x"]
TradeSide = Literal["buy", "sell"]
TradeStatus = Literal["open", "closed"]
TradeMode = Literal["paper", "real"]


@dataclass
class Poll:
    poll_id: str
    question: str
    url: str
    category: Optional[str]
    end_time: int
    status: Optional[str]
    archived: int = 0


@dataclass
class Outcome:
    outcome_id: str
    poll_id: str
    name: str
    price: Optional[float]
    last_price_at: Optional[int]
    price_source: Optional[str]


@dataclass
class Research:
    id: str
    poll_id: str
    started_at: Optional[int]
    completed_at: Optional[int]
    recommendation: Optional[Recommendation]
    confidence: Optional[float]
    position_size_pct: Optional[float]
    rationale: Optional[str]
    provider: Optional[str]
    meta_json: Optional[str]


@dataclass
class Citation:
    id: str
    research_id: str
    kind: CitationKind
    title: Optional[str]
    url: str
    snippet: Optional[str]
    source: Optional[str]
    published_at: Optional[int]


@dataclass
class Trade:
    id: str
    poll_id: str
    research_id: Optional[str]
    outcome_id: str
    side: TradeSide
    size_usdc: float
    quantity: float
    entry_price: float
    entry_time: int
    exit_price: Optional[float]
    exit_time: Optional[int]
    status: TradeStatus
    mode: TradeMode
    provider: Optional[str]
    provider_order_id: Optional[str]
    fee: Optional[float]


@dataclass
class AgentDecisions:
    processed: int
    entered: int
    skipped: int


