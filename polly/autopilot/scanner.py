"""Opportunity scanner for finding trading opportunities."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from polly.models import Market, MarketGroup
from polly.services.polymarket import PolymarketService
from polly.storage.trades import TradeRepository


@dataclass
class Opportunity:
    """A potential trading opportunity."""
    item: Market | MarketGroup
    score: float
    reason: str


class OpportunityScanner:
    """Scan all markets for trading opportunities."""
    
    def __init__(self, trade_repo: TradeRepository):
        self.trade_repo = trade_repo
        self.logger = logging.getLogger("autopilot.scanner")
    
    async def scan_for_edge(
        self,
        polymarket: PolymarketService,
        max_candidates: int = 5
    ) -> List[Opportunity]:
        """Scan markets and find top opportunities.
        
        Strategy:
        1. Fetch all markets/groups
        2. Filter to promising candidates
        3. Quick-score without full research
        4. Return top N for research
        
        Args:
            polymarket: Polymarket service instance
            max_candidates: Maximum opportunities to return
            
        Returns:
            List of top opportunities sorted by score
        """
        self.logger.info("🔎 Scanning markets for opportunities...")
        
        # Fetch all markets
        items = await polymarket.fetch_all_markets()
        self.logger.debug(f"  Fetched {len(items)} total items")
        
        # Filter to promising candidates
        candidates = self._filter_candidates(items)
        self.logger.debug(f"  Filtered to {len(candidates)} promising candidates")
        
        if not candidates:
            self.logger.info("  No promising candidates found")
            return []
        
        # Quick score
        scored = self._quick_score(candidates)
        
        # Return top N
        top_opportunities = scored[:max_candidates]
        
        self.logger.info(f"  Found {len(top_opportunities)} top opportunities:")
        for opp in top_opportunities:
            title = opp.item.title if isinstance(opp.item, MarketGroup) else opp.item.question
            self.logger.info(f"    • {title[:50]} (score: {opp.score:.0f}, {opp.reason})")
        
        return top_opportunities
    
    def _filter_candidates(self, items: List[Market | MarketGroup]) -> List[Market | MarketGroup]:
        """Filter to markets worth researching.
        
        Criteria:
        - Not already holding position
        - 7-180 days to expiry (sweet spot)
        - Liquidity >$50k (minimum threshold)
        - Volume >$1k (shows market activity)
        """
        filtered = []
        now = datetime.now(tz=timezone.utc)
        
        for item in items:
            # Skip if already have position
            if self._already_have_position(item):
                continue
            
            # Check expiry window (7-180 days)
            days_to_expiry = (item.end_date - now).days
            if days_to_expiry < 7 or days_to_expiry > 180:
                continue
            
            # Skip if liquidity too low
            if item.liquidity < 50_000:
                continue
            
            # Skip if no volume (inactive market)
            if item.volume_24h < 1_000:
                continue
            
            filtered.append(item)
        
        return filtered
    
    def _already_have_position(self, item: Market | MarketGroup) -> bool:
        """Check if we already have an active position in this market/event."""
        try:
            # For grouped events, check by event_id
            if isinstance(item, MarketGroup):
                active = self.trade_repo.list_active(filter_mode="real")
                for trade in active:
                    if trade.event_id == item.id:
                        return True
            else:
                # For single markets, check by market_id
                latest = self.trade_repo.find_latest_by_market(item.id)
                if latest and latest.status == "active":
                    return True
            return False
        except Exception:
            return False
    
    def _quick_score(self, candidates: List[Market | MarketGroup]) -> List[Opportunity]:
        """Quick scoring without full research.
        
        Scores based on:
        - Odds competitiveness (not 95/5 blowout)
        - Liquidity (higher = safer/better)
        - Time to expiry (30-90 day sweet spot)
        - Volume (indicates action and information flow)
        
        Returns:
            Sorted list of opportunities (highest score first)
        """
        scored = []
        now = datetime.now(tz=timezone.utc)
        
        for item in candidates:
            score = 0.0
            reasons = []
            
            # 1. Competitive odds (most important)
            if isinstance(item, MarketGroup):
                # For groups, check if multiple viable candidates
                top_markets = item.get_top_markets(3)
                if top_markets:
                    # Get Yes probabilities
                    top_probs = []
                    for m in top_markets:
                        yes_prob = next((o.price for o in m.outcomes if o.outcome.lower() in ('yes', 'y')), 0.0)
                        top_probs.append(yes_prob)
                    
                    # Competitive if top candidate <80%
                    if top_probs[0] < 0.80:
                        score += 10
                        reasons.append("competitive")
                    
                    # Extra points if multiple viable (>10% each)
                    viable_count = sum(1 for p in top_probs if p > 0.10)
                    if viable_count >= 2:
                        score += 5
                        reasons.append(f"{viable_count} viable candidates")
            else:
                # Binary market - check if competitive
                max_odds = max(o.price for o in item.outcomes) if item.outcomes else 1.0
                if max_odds < 0.80:
                    score += 10
                    reasons.append("competitive odds")
            
            # 2. High liquidity (safety and tradability)
            if item.liquidity > 5_000_000:
                score += 8
                reasons.append("very high liquidity")
            elif item.liquidity > 1_000_000:
                score += 5
                reasons.append("high liquidity")
            elif item.liquidity > 500_000:
                score += 3
                reasons.append("good liquidity")
            
            # 3. Sweet spot timing (30-90 days)
            days = (item.end_date - now).days
            if 30 <= days <= 90:
                score += 5
                reasons.append("optimal timing")
            elif 15 <= days <= 120:
                score += 2
                reasons.append("good timing")
            
            # 4. Active trading (volume)
            if item.volume_24h > 100_000:
                score += 5
                reasons.append("very active")
            elif item.volume_24h > 10_000:
                score += 3
                reasons.append("active trading")
            elif item.volume_24h > 5_000:
                score += 1
                reasons.append("moderate volume")
            
            # 5. Group bonus (multi-outcome events have more hedge potential)
            if isinstance(item, MarketGroup) and len(item.markets) > 5:
                score += 2
                reasons.append(f"{len(item.markets)} candidates")
            
            title = item.title if isinstance(item, MarketGroup) else item.question
            scored.append(Opportunity(
                item=item,
                score=score,
                reason=", ".join(reasons)
            ))
        
        # Sort by score (highest first)
        return sorted(scored, key=lambda x: x.score, reverse=True)

