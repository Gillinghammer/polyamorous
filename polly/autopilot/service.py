"""Autonomous trading service - runs continuously in background."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from polly.autopilot.logging_config import setup_logging
from polly.autopilot.scanner import OpportunityScanner, Opportunity
from polly.autopilot.wallet import WalletManager
from polly.config import load_config, AppConfig
from polly.models import Market, MarketGroup, ResearchProgress, Trade
from polly.services.evaluator import PositionEvaluator
from polly.services.polymarket import PolymarketService
from polly.services.research import ResearchService
from polly.services.trading import TradingService
from polly.storage.trades import TradeRepository


class AutopilotService:
    """Autonomous trading service that runs continuously.
    
    Responsibilities:
    - Monitor active positions every hour
    - Re-research when triggers detected
    - Execute trades (enter/exit/adjust)
    - Scan for new opportunities
    - Optimize portfolio allocation
    - Log all decisions and actions
    """
    
    def __init__(self, config_path: Path):
        # Load environment variables
        load_dotenv()
        
        self.config = load_config(config_path)
        self.logger = setup_logging()
        self.running = False
        self.cycle_count = 0
        self.start_time = None
        
        # Initialize core services
        self.polymarket = PolymarketService(self.config.polls)
        self.research_service = ResearchService(self.config.research)
        self.evaluator = PositionEvaluator(self.config.research)
        self.trade_repo = TradeRepository(self.config.database_path)
        
        # Initialize trading service (real wallet mode)
        self.trading_service = self._create_trading_service()
        
        # Initialize wallet manager
        self.wallet_manager = WalletManager(self.trading_service, self.config)
        
        # Initialize scanner
        self.scanner = OpportunityScanner(self.trade_repo)
        
        self.logger.info("Autopilot service initialized")
        self.logger.info(f"Config: {config_path}")
        self.logger.info(f"Mode: {self.config.trading.mode}")
    
    def _create_trading_service(self) -> Optional[TradingService]:
        """Create trading service with real wallet."""
        private_key = os.getenv("POLYGON_PRIVATE_KEY")
        if not private_key:
            self.logger.error("POLYGON_PRIVATE_KEY not set - autopilot requires real trading mode")
            return None
        
        try:
            return TradingService(
                private_key=private_key,
                chain_id=self.config.trading.chain_id,
                host=self.config.trading.clob_host,
                signature_type=self.config.trading.signature_type,
                funder=self.config.trading.polymarket_proxy_address or "",
            )
        except Exception as e:
            self.logger.error(f"Error initializing trading service: {e}", exc_info=True)
            return None
    
    async def run(self):
        """Main service loop - runs until stopped."""
        self.running = True
        self.start_time = datetime.now(tz=timezone.utc)
        
        self.logger.info("="*60)
        self.logger.info("🚀 Polly Autopilot Service Started")
        self.logger.info("="*60)
        self.logger.info(f"Started at: {self.start_time.isoformat()}")
        self.logger.info(f"Check interval: {self.config.trading.price_refresh_seconds}s")
        self.logger.info("="*60)
        
        if not self.trading_service:
            self.logger.error("❌ Trading service unavailable - autopilot cannot run")
            self.logger.error("Set POLYGON_PRIVATE_KEY environment variable")
            return
        
        while self.running:
            try:
                await self.execute_trading_cycle()
                self.cycle_count += 1
                
                # Sleep until next cycle
                sleep_seconds = self.config.trading.price_refresh_seconds
                self.logger.debug(f"Sleeping {sleep_seconds}s until next cycle...")
                await asyncio.sleep(sleep_seconds)
                
            except KeyboardInterrupt:
                self.logger.info("Autopilot stopped by user (Ctrl+C)")
                break
            except Exception as e:
                self.logger.error(f"Cycle error: {e}", exc_info=True)
                self.logger.warning("Waiting 60s before retry...")
                await asyncio.sleep(60)  # Wait 1 min on error
        
        uptime = datetime.now(tz=timezone.utc) - self.start_time
        self.logger.info("="*60)
        self.logger.info(f"Autopilot stopped after {self.cycle_count} cycles")
        self.logger.info(f"Uptime: {uptime}")
        self.logger.info("="*60)
    
    async def execute_trading_cycle(self):
        """Execute one complete trading cycle.
        
        Cycle steps:
        1. Check wallet balance
        2. Monitor existing positions
        3. Scan for new opportunities (future)
        4. Risk checks
        """
        cycle_start = datetime.now(tz=timezone.utc)
        
        self.logger.info("")
        self.logger.info("="*60)
        self.logger.info(f"Cycle {self.cycle_count + 1} started")
        self.logger.info("="*60)
        
        # Step 1: Refresh wallet balance
        balance = await self.wallet_manager.get_available_balance()
        self.logger.info(f"💰 Available balance: ${balance:.2f} USDC")
        
        # Step 2: Monitor existing positions
        await self.monitor_positions(balance)
        
        # Step 3: Scan for new opportunities
        await self.scan_opportunities(balance)
        
        # Step 4: Future - Portfolio optimization
        # await self.optimize_portfolio(balance)
        
        # Step 5: Risk checks
        await self.check_risk_limits()
        
        duration = (datetime.now(tz=timezone.utc) - cycle_start).total_seconds()
        self.logger.info(f"✓ Cycle {self.cycle_count + 1} completed in {duration:.1f}s")
    
    async def monitor_positions(self, available_balance: float):
        """Monitor all active positions and take actions if needed."""
        
        # Get active real trades only
        active_trades = self.trade_repo.list_active(filter_mode="real")
        
        if not active_trades:
            self.logger.info("📊 No active positions to monitor")
            return
        
        self.logger.info(f"📊 Monitoring {len(active_trades)} active position(s)...")
        
        for trade in active_trades:
            await self._monitor_single_position(trade, available_balance)
    
    async def _monitor_single_position(self, trade: Trade, available_balance: float):
        """Monitor a single position."""
        
        self.logger.info("")
        self.logger.info("─"*40)
        self.logger.info(f"Position #{trade.id}: {trade.question[:50]}")
        
        try:
            # Fetch current market state
            market = await self.polymarket.fetch_market_by_id(trade.market_id)
            
            if not market:
                self.logger.warning(f"  ⚠️  Could not fetch market - may be resolved or delisted")
                return
            
            # Get current odds
            current_odds = 0.0
            for outcome in market.outcomes:
                if outcome.outcome == trade.selected_option:
                    current_odds = outcome.price
                    break
            
            # Calculate metrics
            days_left = (trade.resolves_at - datetime.now(tz=timezone.utc)).days
            entry_odds = trade.entry_odds
            odds_change = current_odds - entry_odds
            
            # Calculate unrealized P&L
            shares = trade.stake_amount / entry_odds if entry_odds > 0 else 0
            current_value = shares * current_odds
            unrealized_pnl = current_value - trade.stake_amount
            
            self.logger.info(f"  Entry: {entry_odds:.1%} → Current: {current_odds:.1%} ({odds_change:+.1%})")
            self.logger.info(f"  Unrealized P&L: ${unrealized_pnl:+.2f}")
            self.logger.info(f"  Days left: {days_left}")
            
            # For now, just monitor - future: add trigger detection and actions
            self.logger.info("  → Hold (monitoring only - actions coming soon)")
            
        except Exception as e:
            self.logger.error(f"  ✗ Error monitoring position: {e}", exc_info=True)
    
    async def scan_opportunities(self, available_balance: float):
        """Scan for new trading opportunities."""
        
        # Need minimum balance to trade
        if available_balance < 20:
            self.logger.info("🔎 Skipping opportunity scan (balance < $20)")
            return
        
        # Check position count
        active_trades = self.trade_repo.list_active(filter_mode="real")
        if len(active_trades) >= 30:
            self.logger.info("🔎 Skipping opportunity scan (max 30 positions)")
            return
        
        try:
            # Scan markets
            opportunities = await self.scanner.scan_for_edge(
                self.polymarket,
                max_candidates=3  # Research top 3 each cycle
            )
            
            if not opportunities:
                self.logger.info("🔎 No new opportunities found this cycle")
                return
            
            # Research and enter opportunities
            for opp in opportunities:
                await self._research_and_enter(opp, available_balance)
                
                # Update balance after entry
                available_balance = await self.wallet_manager.get_available_balance()
                
                # Stop if balance too low
                if available_balance < 20:
                    self.logger.info("  Balance now < $20, stopping opportunity search")
                    break
            
        except Exception as e:
            self.logger.error(f"Error scanning opportunities: {e}", exc_info=True)
    
    async def _research_and_enter(self, opportunity: Opportunity, available_balance: float):
        """Research an opportunity and enter positions if edge found.
        
        Args:
            opportunity: The opportunity to research
            available_balance: Current available wallet balance
        """
        title = opportunity.item.title if isinstance(opportunity.item, MarketGroup) else opportunity.item.question
        self.logger.info(f"")
        self.logger.info(f"🔍 Researching opportunity: {title[:60]}")
        self.logger.info(f"   Score: {opportunity.score:.0f} ({opportunity.reason})")
        
        try:
            # Run research
            if isinstance(opportunity.item, MarketGroup):
                research = await self.research_service.research_market_group(
                    group=opportunity.item,
                    callback=lambda p: self.logger.debug(f"   Research: {p.message}"),
                )
                self.logger.info(f"   ✓ Group research completed: {len(research.recommendations)} recommendations")
            else:
                research = await self.research_service.conduct_research(
                    market=opportunity.item,
                    callback=lambda p: self.logger.debug(f"   Research: {p.message}"),
                )
                self.logger.info(f"   ✓ Research completed: {research.prediction} @ {research.probability:.1%}")
            
            # Evaluate and enter positions
            if isinstance(opportunity.item, MarketGroup):
                await self._enter_group_positions(opportunity.item, research, available_balance)
            else:
                await self._enter_single_position(opportunity.item, research, available_balance)
                
        except Exception as e:
            self.logger.error(f"   ✗ Error researching/entering: {e}", exc_info=True)
    
    async def _enter_single_position(self, market: Market, research, available_balance: float):
        """Enter a position on a single binary market."""
        
        # Evaluate if should enter
        evaluation = self.evaluator.evaluate(market, research)
        
        if evaluation.recommendation != "enter":
            self.logger.info(f"   → PASS: {evaluation.rationale}")
            return
        
        # Find the outcome token
        outcome_token = None
        for outcome in market.outcomes:
            if outcome.outcome == research.prediction:
                outcome_token = outcome
                break
        
        if not outcome_token:
            self.logger.error(f"   ✗ Could not find outcome token for {research.prediction}")
            return
        
        # Calculate position size
        current_exposure = sum(t.stake_amount for t in self.trade_repo.list_active(filter_mode="real"))
        safe_stake = self.wallet_manager.calculate_position_size(
            recommended_stake=self.config.trading.default_stake,
            available_balance=available_balance,
            current_exposure=current_exposure
        )
        
        # Lower minimum for smaller balances
        min_trade = 1.50  # $1.50 minimum (allows trading with very small balances)
        if safe_stake < min_trade:
            self.logger.info(f"   → SKIP: Position too small (${safe_stake:.2f} < ${min_trade} minimum)")
            return
        
        self.logger.info(f"   💰 Position sizing: Recommended ${self.config.trading.default_stake} → Actual ${safe_stake:.2f}")
        self.logger.info(f"   ➕ ENTERING ${safe_stake:.2f} on {research.prediction} @ {outcome_token.price:.1%}")
        
        try:
            # Execute trade
            shares = safe_stake / outcome_token.price if outcome_token.price > 0 else 0
            result = self.trading_service.execute_market_buy(outcome_token.token_id, shares)
            
            if not result.success:
                self.logger.error(f"   ✗ Trade failed: {result.error}")
                return
            
            # Record trade
            trade = Trade(
                id=None,
                market_id=market.id,
                question=market.question,
                category=market.category,
                selected_option=research.prediction,
                entry_odds=result.executed_price,
                stake_amount=safe_stake,
                entry_timestamp=datetime.now(tz=timezone.utc),
                predicted_probability=research.probability,
                confidence=research.confidence,
                research_id=None,
                status="active",
                resolves_at=market.end_date,
                actual_outcome=None,
                profit_loss=None,
                closed_at=None,
                trade_mode="real",
                order_id=result.order_id,
            )
            
            try:
                saved_trade = self.trade_repo.record_trade(trade)
                self.logger.info(f"   ✓ Position #{saved_trade.id} created: ${safe_stake:.2f} @ {result.executed_price:.1%}")
                self.logger.info(f"   📊 Edge: {research.probability - result.executed_price:+.1%}, Confidence: {research.confidence:.0f}%")
            except Exception as db_error:
                self.logger.error(f"   ✗ Database error saving trade: {db_error}", exc_info=True)
                # Still log the on-chain position even if DB fails
                self.logger.info(f"   ⚠️  Position created on-chain but not saved to DB: Order {result.order_id}")
            
            # Log to trades.log
            logging.getLogger("trades").info(
                f"ENTER | #{saved_trade.id} | {market.question[:50]} | "
                f"${safe_stake:.2f} @ {result.executed_price:.1%} | "
                f"Edge: {research.probability - result.executed_price:+.1%}"
            )
            
        except Exception as e:
            self.logger.error(f"   ✗ Error executing trade: {e}", exc_info=True)
    
    async def _enter_group_positions(self, group: MarketGroup, research, available_balance: float):
        """Enter multiple positions from grouped event research."""
        
        if not research.recommendations:
            self.logger.info(f"   → PASS: No recommendations from research")
            return
        
        # Filter to entry-suggested only
        to_enter = [r for r in research.recommendations if r.entry_suggested]
        
        if not to_enter:
            self.logger.info(f"   → PASS: No positions suggested for entry")
            return
        
        self.logger.info(f"   💼 Group strategy: {len(to_enter)} positions recommended")
        
        # Calculate total and scale to balance
        total_recommended = sum(r.suggested_stake for r in to_enter)
        current_exposure = sum(t.stake_amount for t in self.trade_repo.list_active(filter_mode="real"))
        
        # Can only use 80% of balance
        max_deployable = available_balance * 0.80
        scale_factor = min(1.0, max_deployable / total_recommended) if total_recommended > 0 else 0
        
        self.logger.info(f"   💰 Scaling: ${total_recommended:.0f} recommended → ${total_recommended * scale_factor:.2f} actual")
        
        entered_positions = []
        for rec in to_enter:
            # Scale the stake
            scaled_stake = rec.suggested_stake * scale_factor
            
            # Apply position limits
            safe_stake = self.wallet_manager.calculate_position_size(
                recommended_stake=scaled_stake,
                available_balance=available_balance,
                current_exposure=current_exposure
            )
            
            # Lower minimum for smaller balances
            min_trade = 1.50  # $1.50 minimum
            if safe_stake < min_trade:
                self.logger.info(f"      → Skip: {rec.market_question[:40]} (${safe_stake:.2f} < ${min_trade})")
                continue
            
            # Find the market - try multiple matching strategies
            market = next((m for m in group.markets if m.id == rec.market_id), None)
            
            # If ID match fails, try matching by question text
            if not market:
                # Extract candidate name from recommendation
                rec_candidate = rec.market_question.split("Will ")[-1].split(" win")[0].strip() if "Will " in rec.market_question else rec.market_question.split(" ")[ 0]
                
                # Try to find by candidate name in question
                for m in group.markets:
                    if rec_candidate.lower() in m.question.lower():
                        market = m
                        self.logger.debug(f"      Matched by name: {rec_candidate} → {m.question[:50]}")
                        break
            
            if not market:
                candidate_name = rec.market_question[:40]
                self.logger.warning(f"      → Skip: Could not find market for {candidate_name}")
                continue
            
            # Find Yes outcome
            yes_outcome = next((o for o in market.outcomes if o.outcome.lower() in ('yes', 'y')), None)
            if not yes_outcome:
                continue
            
            candidate_name = market.question.split("Will ")[-1].split(" win")[0] if "Will " in market.question else market.question[:30]
            
            self.logger.info(f"      ➕ Entering ${safe_stake:.2f} on {candidate_name} @ {yes_outcome.price:.1%}")
            
            try:
                # Execute
                shares = safe_stake / yes_outcome.price if yes_outcome.price > 0 else 0
                result = self.trading_service.execute_market_buy(yes_outcome.token_id, shares)
                
                if not result.success:
                    self.logger.error(f"      ✗ Failed: {result.error}")
                    continue
                
                # Record trade
                trade = Trade(
                    id=None,
                    market_id=market.id,
                    question=market.question,
                    category=group.category,
                    selected_option="Yes",
                    entry_odds=result.executed_price,
                    stake_amount=safe_stake,
                    entry_timestamp=datetime.now(tz=timezone.utc),
                    predicted_probability=rec.probability,
                    confidence=rec.confidence,
                    research_id=None,
                    status="active",
                    resolves_at=group.end_date,
                    actual_outcome=None,
                    profit_loss=None,
                    closed_at=None,
                    trade_mode="real",
                    order_id=result.order_id,
                    event_id=group.id,
                    event_title=group.title,
                    is_grouped=True,
                    group_strategy="multi_position_hedge"
                )
                
                try:
                    saved = self.trade_repo.record_trade(trade)
                    entered_positions.append(saved)
                    self.logger.info(f"      ✓ Position #{saved.id} created")
                except Exception as db_error:
                    self.logger.error(f"      ✗ Database error: {db_error}", exc_info=True)
                    # Still track that trade was made on-chain
                    self.logger.info(f"      ⚠️  On-chain but not in DB: Order {result.order_id}")
                
                # Update available balance and exposure
                available_balance -= safe_stake
                current_exposure += safe_stake
                
            except Exception as e:
                self.logger.error(f"      ✗ Error: {e}", exc_info=True)
        
        if entered_positions:
            total_deployed = sum(t.stake_amount for t in entered_positions)
            self.logger.info(f"   ✓ Entered {len(entered_positions)} positions, total: ${total_deployed:.2f}")
            
            # Log to trades.log
            logging.getLogger("trades").info(
                f"GROUP_ENTER | {group.title[:50]} | "
                f"{len(entered_positions)} positions | ${total_deployed:.2f}"
            )
        else:
            self.logger.info(f"   → No positions entered (all too small or failed)")
    
    async def check_risk_limits(self):
        """Check portfolio-level risk limits."""
        
        # Get all active trades
        active_trades = self.trade_repo.list_active(filter_mode="real")
        
        if not active_trades:
            return
        
        # Calculate total exposure
        total_exposure = sum(t.stake_amount for t in active_trades)
        
        # Get balance
        balance = await self.wallet_manager.get_available_balance()
        total_portfolio = balance + total_exposure
        
        # Check utilization
        utilization = total_exposure / total_portfolio if total_portfolio > 0 else 0
        
        self.logger.info(f"")
        self.logger.info(f"💼 Portfolio: ${total_portfolio:.2f} total (${balance:.2f} cash, ${total_exposure:.2f} in positions)")
        self.logger.info(f"📊 Utilization: {utilization:.1%}")
        
        # Warn if over-utilized
        if utilization > 0.90:
            self.logger.warning("⚠️  Portfolio >90% utilized - consider rebalancing")
        
        # Future: Add drawdown checks, correlation limits, etc.

