"""Client wrapper for fetching Polymarket markets."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from importlib import import_module, util
from typing import Iterable, List
import requests

from polly.config import PollConfig
from polly.models import Market, MarketGroup, MarketOutcome


HOST = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"


@dataclass
class PolymarketService:
    """Service responsible for fetching and formatting markets."""

    poll_config: PollConfig

    def __post_init__(self) -> None:
        self._client = self._create_client()

    async def fetch_top_markets(self) -> List[Market | MarketGroup]:
        """Fetch the top configured markets (first page)."""
        return await self.fetch_markets_page(page=1, page_size=self.poll_config.top_n)

    async def fetch_markets_page(self, page: int, page_size: int) -> List[Market | MarketGroup]:
        """Fetch a page of markets using the canonical endpoint and filters."""
        return await asyncio.to_thread(self._fetch_markets_sync, page, page_size)

    async def fetch_all_markets(self) -> List[Market | MarketGroup]:
        """Fetch all active filtered markets and market groups (no slicing)."""
        return await asyncio.to_thread(self._fetch_markets_sync, None)

    async def fetch_market_by_id(self, condition_id: str) -> Market | None:
        """Fetch a single market by condition_id.
        
        Searches both individual markets and markets within groups.
        """
        def _inner() -> Market | None:
            all_items = self._fetch_markets_sync(None)
            
            for item in all_items:
                # Check if it's a direct market match
                if isinstance(item, Market) and item.id == condition_id:
                    return item
                
                # Check if it's inside a MarketGroup
                if isinstance(item, MarketGroup):
                    for market in item.markets:
                        if market.id == condition_id:
                            return market
            
            return None
        return await asyncio.to_thread(_inner)

    async def fetch_markets_by_ids(self, condition_ids: list[str]) -> List[Market]:
        """Fetch multiple markets by condition_ids."""
        ids_set = set(condition_ids)
        def _inner() -> List[Market]:
            all_markets = self._fetch_markets_sync(None)
            return [m for m in all_markets if m.id in ids_set]
        return await asyncio.to_thread(_inner)

    def _create_client(self):
        """Instantiate the py_clob_client if available."""

        if util.find_spec("py_clob_client.client") is None:
            return None

        module = import_module("py_clob_client.client")
        client = getattr(module, "ClobClient")(HOST)
        return client
    
    def _is_multi_outcome_event(self, event: dict) -> bool:
        """Check if event should be treated as grouped multi-outcome market."""
        markets = event.get("markets", [])
        return (
            len(markets) > 1 
            and (event.get("enableNegRisk") or event.get("showAllOutcomes"))
        )
    
    def _create_market_group(self, event: dict) -> MarketGroup:
        """Build MarketGroup from event data."""
        # Extract event metadata
        event_id = event.get("id", "")
        title = event.get("title", "")
        description = event.get("description", "")
        
        # Extract category from tags
        event_tags = event.get("tags", [])
        category = "Other"
        tag_labels = []
        
        if isinstance(event_tags, list):
            for tag in event_tags:
                if isinstance(tag, dict):
                    label = tag.get("label")
                    if label:
                        tag_labels.append(label)
                        if category == "Other":  # Use first tag as category
                            category = label
        
        # Get end date
        end_date_iso = event.get("endDate")
        if end_date_iso:
            try:
                end_date = datetime.fromisoformat(str(end_date_iso).replace("Z", "+00:00"))
            except:
                end_date = datetime.now(tz=timezone.utc) + timedelta(days=365)
        else:
            end_date = datetime.now(tz=timezone.utc) + timedelta(days=365)
        
        # Convert each market in event to Market object
        markets = []
        for market_dict in event.get("markets", []):
            if not isinstance(market_dict, dict):
                continue
            
            # Enrich with event context
            market_dict["event_id"] = event_id
            market_dict["event_title"] = title
            market_dict["event_category"] = category
            market_dict["event_tags"] = event_tags
            market_dict["event_liquidity"] = event.get("liquidity", 0)
            market_dict["event_volume"] = event.get("volume", 0)
            market_dict["event_volume24hr"] = event.get("volume24hr", 0)
            market_dict["endDate"] = end_date_iso or market_dict.get("endDate")
            
            # Convert to Market object
            market = self._convert_market(market_dict)
            market.event_id = event_id
            market.event_title = title
            market.is_grouped = True
            markets.append(market)
        
        return MarketGroup(
            id=event_id,
            title=title,
            description=description,
            category=category,
            tags=tag_labels,
            end_date=end_date,
            liquidity=float(event.get("liquidity", 0)),
            volume_24h=float(event.get("volume24hr", 0)),
            enable_neg_risk=bool(event.get("enableNegRisk", False)),
            show_all_outcomes=bool(event.get("showAllOutcomes", False)),
            markets=markets,
            resolution_source=event.get("resolutionSource", "")
        )

    def _fetch_markets_sync(self, page: int | None = 1, page_size: int = 20) -> List[Market | MarketGroup]:
        """Fetch and return both individual markets and grouped events."""
        
        # Fetch from Gamma API /events endpoint
        try:
            response = requests.get(
                f"{GAMMA_API}/events",
                params={"closed": "false", "limit": 1000, "archived": "false"},
                timeout=30
            )
            response.raise_for_status()
            raw_events = response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch events from Gamma API: {e}")
        
        # Process each event - decide if it's a group or individual market
        items = []  # Will contain Market or MarketGroup objects
        now = datetime.now(tz=timezone.utc)
        
        if isinstance(raw_events, list):
            for event in raw_events:
                if not isinstance(event, dict):
                    continue
                
                # Skip archived/closed events
                if event.get("archived", False) or event.get("closed", False):
                    continue
                
                # Check if this is a multi-outcome grouped event
                if self._is_multi_outcome_event(event):
                    # Create MarketGroup
                    try:
                        group = self._create_market_group(event)
                        # Apply basic filters to the group
                        if self._should_include_group(group):
                            items.append(group)
                    except Exception:
                        # If group creation fails, skip this event
                        continue
                else:
                    # Single market event - extract the market
                    event_markets = event.get("markets", [])
                    if isinstance(event_markets, list) and len(event_markets) == 1:
                        market_dict = event_markets[0]
                        if isinstance(market_dict, dict):
                            # Enrich with event context
                            event_tags = event.get("tags", [])
                            event_category = None
                            if isinstance(event_tags, list) and event_tags:
                                for tag in event_tags:
                                    if isinstance(tag, dict) and tag.get("label"):
                                        event_category = tag.get("label")
                                        break
                            
                            market_dict["event_title"] = event.get("title", "")
                            market_dict["event_description"] = event.get("description", "")
                            market_dict["event_category"] = event_category or "Other"
                            market_dict["event_tags"] = event_tags
                            market_dict["event_liquidity"] = event.get("liquidity", 0)
                            market_dict["event_volume"] = event.get("volume", 0)
                            market_dict["event_volume24hr"] = event.get("volume24hr", 0)
                            market_dict["endDate"] = event.get("endDate") or market_dict.get("endDate")
                            
                            # Apply market-level filters
                            if self._should_include_market_dict(market_dict, now):
                                market = self._convert_market(market_dict)
                                items.append(market)
        
        # Sort by liquidity score
        items_sorted = self._sort_items(items)
        
        # Simple pagination via slicing
        if page is None:
            return items_sorted
        start = max((int(page) - 1) * page_size, 0)
        end = max(start + page_size, 0)
        return items_sorted[start:end]
    
    def _should_include_group(self, group: MarketGroup) -> bool:
        """Check if a market group should be included based on filters."""
        # Check if expired
        now = datetime.now(tz=timezone.utc)
        if group.end_date <= now:
            return False
        
        # Check if sports/esports
        exclude_tokens = {category.lower() for category in self.poll_config.exclude_categories}
        if _is_sports_market_group(group, exclude_tokens):
            return False
        
        # Check if has sufficient liquidity (use group total)
        if not _has_sufficient_liquidity_value(group.liquidity):
            return False
        
        # Check if any market in group has non-extreme odds (at least one viable option)
        has_viable_market = False
        for market in group.markets:
            if not _has_extreme_odds_market(market):
                has_viable_market = True
                break
        
        return has_viable_market
    
    def _should_include_market_dict(self, market_dict: dict, now: datetime) -> bool:
        """Check if a market dict should be included based on filters."""
        # Check archived/active/closed
        if market_dict.get("archived", False):
            return False
        if not market_dict.get("active", True):
            return False
        if market_dict.get("closed", False):
            return False
        
        # Check end date
        end_iso = market_dict.get("endDate")
        if not end_iso:
            return False
        try:
            end_dt = datetime.fromisoformat(str(end_iso).replace("Z", "+00:00"))
        except:
            return False
        if end_dt <= now:
            return False
        
        # Check has prices
        if not (market_dict.get("outcomePrices") is not None and market_dict.get("outcomes")):
            return False
        
        # Check sports
        exclude_tokens = {category.lower() for category in self.poll_config.exclude_categories}
        if _is_sports_market(market_dict, exclude_tokens):
            return False
        
        # Check extreme odds
        if _has_extreme_odds(market_dict):
            return False
        
        # Check liquidity (with event fallback)
        liquidity = float(
            market_dict.get("liquidityNum")
            or market_dict.get("liquidity")
            or market_dict.get("event_liquidity")
            or 0.0
        )
        if not _has_sufficient_liquidity_value(liquidity):
            return False
        
        return True
    
    def _sort_items(self, items: List[Market | MarketGroup]) -> List[Market | MarketGroup]:
        """Sort items by liquidity score."""
        def get_liquidity_score(item):
            if isinstance(item, MarketGroup):
                # Use group total liquidity for scoring
                return item.liquidity * self.poll_config.liquidity_weight_open_interest + \
                       item.volume_24h * self.poll_config.liquidity_weight_volume_24h
            else:
                # Market - calculate as before
                return self._liquidity_score_for_market(item)
        
        return sorted(items, key=get_liquidity_score, reverse=True)
    
    def _liquidity_score_for_market(self, market: Market) -> float:
        """Calculate liquidity score for a Market object."""
        return (
            market.liquidity * self.poll_config.liquidity_weight_open_interest
            + market.volume_24h * self.poll_config.liquidity_weight_volume_24h
        )

    def _transform_markets(self, raw_markets: Iterable[dict]) -> List[Market]:
        """Convert raw markets to domain objects using configured filters."""

        now = datetime.now(tz=timezone.utc)
        active: list[dict] = []
        for market in raw_markets:
            if not isinstance(market, dict):
                continue
            if market.get("archived", False):
                continue
            if not market.get("active", True):
                continue
            if market.get("closed", False):
                continue
            
            # Handle both Gamma API (endDate) and CLOB API (end_date_iso) formats
            end_iso = market.get("endDate") or market.get("end_date_iso") or market.get("game_start_time")
            if not end_iso:
                continue
            try:
                end_dt = datetime.fromisoformat(str(end_iso).replace("Z", "+00:00"))
            except Exception:
                continue
            if end_dt <= now:
                continue
            
            # Gamma API uses outcomePrices, CLOB uses tokens
            # Skip markets without valid prices
            if market.get("tokens"):
                # CLOB format
                has_prices = True
            elif market.get("outcomePrices") is not None and market.get("outcomes"):
                # Gamma format - make sure outcomePrices is not None
                has_prices = True
            else:
                continue
            
            active.append(market)

        exclude_tokens = {category.lower() for category in self.poll_config.exclude_categories}
        filtered = [
            market
            for market in active
            if not _is_sports_market(market, exclude_tokens)
            and not _has_extreme_odds(market)
            and _has_sufficient_liquidity(market)
        ]

        for market in filtered:
            market["liquidity_score"] = self._liquidity_score(market)

        sorted_markets = sorted(
            filtered,
            key=lambda m: m.get("liquidity_score", 0.0),
            reverse=True,
        )

        return [self._convert_market(market) for market in sorted_markets]

    def _liquidity_score(self, market: dict) -> float:
        """Calculate liquidity score using config weights."""

        # Gamma API uses liquidityNum, CLOB uses liquidity
        # Try market-level first, fall back to event-level data
        open_interest = float(
            market.get("liquidityNum")
            or market.get("liquidity")
            or market.get("event_liquidity")
            or market.get("open_interest")
            or market.get("oi")
            or 0.0
        )
        
        # Gamma API uses volume24hr, CLOB uses various keys
        # Try market-level first, fall back to event-level data
        volume = 0.0
        for key in ("volume24hr", "event_volume24hr", "volume24h", "volume_24h", "volume24", "volumeNum", "volume", "event_volume"):
            if market.get(key) is not None:
                try:
                    volume = float(market.get(key))
                    break
                except Exception:
                    volume = 0.0
        
        return (
            open_interest * self.poll_config.liquidity_weight_open_interest
            + volume * self.poll_config.liquidity_weight_volume_24h
        )

    def _convert_market(self, market: dict) -> Market:
        """Map dictionary structure into our Market dataclass."""

        # Resolution / end time - handle both Gamma and CLOB formats
        end_date_iso = market.get("endDate") or market.get("end_date_iso") or market.get("game_start_time")
        end_date = datetime.fromisoformat(str(end_date_iso).replace("Z", "+00:00"))
        
        # Handle outcomes - Gamma API uses outcomePrices/outcomes, CLOB uses tokens
        outcomes = []
        if market.get("tokens"):
            # CLOB API format
            outcomes = [
                MarketOutcome(
                    token_id=token["token_id"],
                    outcome=token.get("outcome", ""),
                    price=float(token.get("price", 0.0)),
                    winner=token.get("winner"),
                )
                for token in market.get("tokens", [])
            ]
        elif market.get("outcomePrices") and market.get("outcomes"):
            # Gamma API format
            import json
            outcome_names = json.loads(market["outcomes"]) if isinstance(market["outcomes"], str) else market["outcomes"]
            outcome_prices = json.loads(market["outcomePrices"]) if isinstance(market["outcomePrices"], str) else market["outcomePrices"]
            token_ids = json.loads(market.get("clobTokenIds", "[]")) if isinstance(market.get("clobTokenIds"), str) else market.get("clobTokenIds", [])
            
            for i, (name, price) in enumerate(zip(outcome_names, outcome_prices)):
                token_id = token_ids[i] if i < len(token_ids) else ""
                outcomes.append(
                    MarketOutcome(
                        token_id=token_id,
                        outcome=name,
                        price=float(price) if price else 0.0,
                        winner=None,
                    )
                )
        
        # Get volume 24h - Gamma uses volume24hr, CLOB uses various keys
        vol_24h = 0.0
        for key in ("volume24hr", "volume24h", "volume_24h", "volume24"):
            if market.get(key) is not None:
                try:
                    vol_24h = float(market.get(key))
                    break
                except Exception:
                    vol_24h = 0.0

        # Try multiple possible field names for the question
        # Prefer market question, fall back to event title
        question = (
            market.get("question") or
            market.get("title") or
            market.get("name") or
            market.get("text") or
            market.get("event_title") or
            market.get("conditionId") or
            market.get("condition_id", "")  # fallback to ID if no question found
        )

        # Category - Try market category first, then event category
        category = market.get("category") or market.get("event_category") or "Other"
        
        # Tags - Merge market tags and event tags, extracting labels from tag objects
        tags = market.get("tags", [])
        event_tags = market.get("event_tags", [])
        if isinstance(tags, str):
            import json
            tags = json.loads(tags) if tags else []
        if isinstance(event_tags, str):
            import json
            event_tags = json.loads(event_tags) if event_tags else []
        
        # Extract tag labels from tag objects
        tag_labels = []
        for tag in (tags if isinstance(tags, list) else []):
            if isinstance(tag, dict):
                label = tag.get("label")
                if label:
                    tag_labels.append(label)
            elif isinstance(tag, str):
                tag_labels.append(tag)
        
        for tag in (event_tags if isinstance(event_tags, list) else []):
            if isinstance(tag, dict):
                label = tag.get("label")
                if label:
                    tag_labels.append(label)
            elif isinstance(tag, str):
                tag_labels.append(tag)
        
        # Combine and deduplicate tags
        all_tags = list(dict.fromkeys(tag_labels))  # Preserve order while deduplicating
        
        # If no category but has tags, use first tag
        if not category or category == "Other":
            if all_tags:
                category = all_tags[0]
        
        # Get liquidity - Gamma uses liquidityNum, CLOB uses liquidity
        # Try market-level first, fall back to event-level
        liquidity_value = float(
            market.get("liquidityNum")
            or market.get("liquidity")
            or market.get("event_liquidity")
            or market.get("open_interest")
            or market.get("liquidity_score")
            or 0.0
        )
        
        # Get resolution source
        resolution_source = market.get("resolutionSource", "").strip()
        
        # Use market description, fall back to event description
        description = market.get("description") or market.get("event_description") or ""
        
        return Market(
            id=market.get("conditionId") or market.get("condition_id"),
            question=question,
            description=description,
            category=category,
            liquidity=liquidity_value,
            volume_24h=vol_24h,
            end_date=end_date,
            outcomes=outcomes,
            tags=all_tags,
            resolution_source=resolution_source,
        )


def filter_by_expiry_days(items: List[Market | MarketGroup], days: int) -> List[Market | MarketGroup]:
    """Filter markets/groups expiring within N days."""
    cutoff = datetime.now(tz=timezone.utc) + timedelta(days=days)
    return [item for item in items if item.end_date <= cutoff]


def _is_sports_market(market: dict, excluded: set[str]) -> bool:
    """Return True if market belongs to an excluded category."""

    # Check event_category since events don't have direct category field
    category = str(market.get("category") or market.get("event_category", "")).lower()
    if any(token in category for token in excluded):
        return True

    # Extract tag labels from both market and event tags
    tags_list = []
    for tag_source in [market.get("tags", []), market.get("event_tags", [])]:
        if isinstance(tag_source, list):
            for tag in tag_source:
                if isinstance(tag, dict):
                    label = tag.get("label", "")
                    if label:
                        tags_list.append(label.lower())
                elif isinstance(tag, str):
                    tags_list.append(tag.lower())
    
    tags_str = " ".join(tags_list)
    return any(token in tags_str for token in excluded)


def _has_extreme_odds(market: dict) -> bool:
    """Return True if any outcome has odds of 80% or higher."""
    
    # Handle CLOB format (tokens)
    tokens = market.get("tokens", []) or []
    for token in tokens:
        try:
            price = float(token.get("price", 0.0))
            if price >= 0.80:
                return True
        except (ValueError, TypeError):
            continue
    
    # Handle Gamma API format (outcomePrices)
    outcome_prices = market.get("outcomePrices")
    if outcome_prices:
        import json
        if isinstance(outcome_prices, str):
            try:
                outcome_prices = json.loads(outcome_prices)
            except:
                return False
        
        for price_str in outcome_prices:
            try:
                price = float(price_str) if price_str else 0.0
                if price >= 0.80:
                    return True
            except (ValueError, TypeError):
                continue
    
    return False


def _has_sufficient_liquidity(market: dict, min_liquidity: float = 50000.0) -> bool:
    """Return True if market has liquidity >= minimum threshold ($50k by default)."""
    
    try:
        # Gamma API uses liquidityNum, CLOB uses liquidity
        # Try market-level first, fall back to event-level data
        liquidity = float(
            market.get("liquidityNum")
            or market.get("liquidity")
            or market.get("event_liquidity")
            or market.get("open_interest")
            or 0.0
        )
        return liquidity >= min_liquidity
    except (ValueError, TypeError):
        return False


def _has_sufficient_liquidity_value(liquidity: float, min_liquidity: float = 50000.0) -> bool:
    """Return True if liquidity value >= minimum threshold ($50k by default)."""
    return liquidity >= min_liquidity


def _is_sports_market_group(group: MarketGroup, excluded: set[str]) -> bool:
    """Return True if market group belongs to an excluded category."""
    # Check category
    category = group.category.lower()
    if any(token in category for token in excluded):
        return True
    
    # Check tags
    tags_str = " ".join(group.tags).lower()
    return any(token in tags_str for token in excluded)


def _has_extreme_odds_market(market: Market) -> bool:
    """Return True if a Market object has any outcome with odds >= 80%."""
    for outcome in market.outcomes:
        if outcome.price >= 0.80:
            return True
    return False


def _offline_markets() -> Iterable[Market]:
    """Provide deterministic sample markets when offline."""

    now = datetime.now(tz=timezone.utc)
    sample = [
        Market(
            id="sample-1",
            question="Will the Senate pass the climate bill by Q4?",
            description="Tracking legislative progress on the pending climate bill.",
            category="Politics",
            liquidity=1_250_000.0,
            volume_24h=250_000.0,
            end_date=now.replace(month=12, day=31, hour=23, minute=59),
            outcomes=[
                MarketOutcome(token_id="sample-1-yes", outcome="Yes", price=0.58),
                MarketOutcome(token_id="sample-1-no", outcome="No", price=0.42),
            ],
            tags=["politics", "legislation"],
        ),
        Market(
            id="sample-2",
            question="Will global AI investment exceed $250B in 2025?",
            description="Assesses total capital deployment into AI companies.",
            category="Economics",
            liquidity=980_000.0,
            volume_24h=190_000.0,
            end_date=now.replace(year=2026, month=1, day=15, hour=12, minute=0),
            outcomes=[
                MarketOutcome(token_id="sample-2-yes", outcome="Yes", price=0.47),
                MarketOutcome(token_id="sample-2-no", outcome="No", price=0.53),
            ],
            tags=["economics", "technology"],
        ),
    ]
    return sample
