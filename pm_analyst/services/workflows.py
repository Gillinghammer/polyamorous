from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

from sqlmodel import select

from ..config import Settings
from ..models.db import Market, Position, Proposal, Research, Trade
from ..services.calculations import EdgeReport, evaluate_market, recommend_stake
from ..services.persistence import session_scope, upsert_markets
from ..services.polymarket import MarketData, PolymarketClient
from ..services.research import ResearchOrchestrator, ResearchResult


@dataclass
class ResearchOutcome:
    market: MarketData
    research: Research
    edge_report: EdgeReport
    result: ResearchResult
    proposal: Optional[Proposal]
    disqualifications: List[str]


@dataclass
class AcceptanceOutcome:
    proposal: Proposal
    trade: Trade
    position: Position
    entry_price: float


def load_filtered_markets(settings: Settings, engine) -> List[MarketData]:
    """Load filtered markets using the configured client and persist snapshots."""

    client = PolymarketClient(settings)
    markets = client.filtered_markets()
    if not markets:
        return []
    with session_scope(engine) as session:
        upsert_markets(session, markets)
        session.commit()
    return markets


def run_research_flow(engine, settings: Settings, market: MarketData) -> ResearchOutcome:
    """Execute the research workflow for a market and persist results."""

    orchestrator = ResearchOrchestrator(settings)
    result = orchestrator.run_research(market.id, market.question)
    edge_report = evaluate_market(result.probability_yes, market.prices, market.resolves_at)

    with session_scope(engine) as session:
        research = Research(
            market_id=market.id,
            probability_yes=result.probability_yes,
            confidence=result.confidence,
            rationale=result.rationale,
            citations=json.dumps(result.citations),
            rounds=result.rounds,
        )
        session.add(research)
        session.commit()
        session.refresh(research)

        disqualifications: List[str] = []
        if result.confidence < settings.research.min_confidence:
            disqualifications.append(
                f"confidence {result.confidence:.0%} below minimum {settings.research.min_confidence:.0%}"
            )
        if edge_report.edge < settings.research.min_edge:
            disqualifications.append(
                f"edge {edge_report.edge:+.2%} below minimum {settings.research.min_edge:.0%}"
            )
        if edge_report.roi <= 0:
            disqualifications.append("negative expected ROI")

        proposal: Optional[Proposal] = None
        if not disqualifications:
            stake = recommend_stake(
                settings.sizing.policy,
                settings.sizing.bankroll,
                settings.sizing.risk_budget,
                result.confidence,
                edge_report.roi,
                settings.sizing.max_fraction,
            )
            if stake <= 0:
                disqualifications.append("stake rounded to zero; proposal skipped")
            else:
                proposal = Proposal(
                    market_id=market.id,
                    side=edge_report.side,
                    stake=stake,
                    edge=edge_report.edge,
                    apr=edge_report.apr,
                    risk_free_apr=settings.risk_free_apr,
                    accepted=False,
                    research_id=research.id,
                )
                session.add(proposal)
                session.commit()
                session.refresh(proposal)

    return ResearchOutcome(
        market=market,
        research=research,
        edge_report=edge_report,
        result=result,
        proposal=proposal,
        disqualifications=disqualifications,
    )


def accept_latest_proposal(
    engine,
    settings: Settings,
    market_id: str,
    stake_override: Optional[float] = None,
    side_override: Optional[str] = None,
) -> AcceptanceOutcome:
    """Accept the most recent proposal for a market and record position impacts."""

    with session_scope(engine) as session:
        proposal: Proposal | None = session.exec(
            select(Proposal).where(Proposal.market_id == market_id).order_by(Proposal.created_at.desc())
        ).first()
        if not proposal:
            raise ValueError("No proposal found. Run research first.")

        if side_override:
            proposal.side = side_override.lower()
        if stake_override is not None:
            if stake_override <= 0:
                raise ValueError("Stake must be positive.")
            proposal.stake = stake_override

        proposal.accepted = True
        session.add(proposal)

        market: Market | None = session.get(Market, proposal.market_id)
        entry_price = 1.0
        if market:
            entry_price = market.price_yes if proposal.side == "yes" else market.price_no
        else:
            fallback = next(
                (
                    m
                    for m in PolymarketClient(settings).filtered_markets()
                    if m.id == proposal.market_id
                ),
                None,
            )
            if fallback:
                entry_price = fallback.prices.get(proposal.side, entry_price)

        trade = Trade(
            market_id=proposal.market_id,
            side=proposal.side,
            stake=proposal.stake,
            entry_price=entry_price,
            research_id=proposal.research_id,
        )
        session.add(trade)

        existing_position = session.exec(
            select(Position).where(Position.market_id == proposal.market_id, Position.status == "open")
        ).first()
        if existing_position:
            total_stake = existing_position.stake + proposal.stake
            if total_stake > 0:
                weighted_entry = (
                    existing_position.entry_price * existing_position.stake
                    + entry_price * proposal.stake
                ) / total_stake
                existing_position.entry_price = weighted_entry
            existing_position.stake = total_stake
            existing_position.mark_price = entry_price
            existing_position.side = proposal.side
            position = existing_position
        else:
            position = Position(
                market_id=proposal.market_id,
                side=proposal.side,
                stake=proposal.stake,
                entry_price=entry_price,
                mark_price=entry_price,
                unrealized_pnl=0.0,
            )
            session.add(position)

        session.commit()
        session.refresh(proposal)
        session.refresh(trade)
        session.refresh(position)

    return AcceptanceOutcome(
        proposal=proposal,
        trade=trade,
        position=position,
        entry_price=entry_price,
    )


__all__ = [
    "ResearchOutcome",
    "AcceptanceOutcome",
    "load_filtered_markets",
    "run_research_flow",
    "accept_latest_proposal",
]
