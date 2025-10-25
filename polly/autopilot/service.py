"""Autonomous trading service - runs continuously in background."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from polly.autopilot.logging_config import setup_logging
from polly.autopilot.wallet import WalletManager
from polly.config import load_config, AppConfig
from polly.models import Trade
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
        
        # Step 3: Future - Scan for new opportunities
        # await self.scan_opportunities(balance)
        
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

