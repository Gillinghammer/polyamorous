from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Market(SQLModel, table=True):
    id: str = Field(primary_key=True)
    slug: str
    question: str
    resolves_at: datetime
    price_yes: float
    price_no: float
    open_interest: float
    volume_24h: float
    depth: float
    category: str
    volatility_hint: float


class Research(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    market_id: str = Field(foreign_key="market.id")
    probability_yes: float
    confidence: float
    rationale: str
    citations: str
    rounds: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Proposal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    market_id: str = Field(foreign_key="market.id")
    side: str
    stake: float
    edge: float
    apr: float
    risk_free_apr: float
    accepted: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    research_id: Optional[int] = Field(default=None, foreign_key="research.id")


class Trade(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    market_id: str = Field(foreign_key="market.id")
    side: str
    stake: float
    entry_price: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    research_id: Optional[int] = Field(default=None, foreign_key="research.id")


class Position(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    market_id: str = Field(foreign_key="market.id")
    side: str
    stake: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    status: str = "open"


class PriceTick(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    market_id: str = Field(foreign_key="market.id")
    price_yes: float
    price_no: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


__all__ = [
    "Market",
    "Research",
    "Proposal",
    "Trade",
    "Position",
    "PriceTick",
]
