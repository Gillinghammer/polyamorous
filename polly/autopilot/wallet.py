"""Wallet management for autopilot service."""

import logging
from typing import Optional

from polly.services.trading import TradingService


class WalletManager:
    """Manage real wallet balance and position sizing."""
    
    def __init__(self, trading_service: Optional[TradingService], config):
        self.trading = trading_service
        self.config = config
        self.gas_reserve = 10.0  # Always keep $10 for gas
        self.logger = logging.getLogger("autopilot.wallet")
    
    async def get_available_balance(self) -> float:
        """Get spendable USDC balance.
        
        Returns available balance after reserving for gas.
        Returns 0 if trading service unavailable or error.
        """
        if not self.trading:
            self.logger.warning("Trading service not available")
            return 0.0
        
        try:
            balances = self.trading.get_balances()
            
            if "error" in balances:
                self.logger.error(f"Error fetching balance: {balances['error']}")
                return 0.0
            
            usdc = float(balances.get("usdc", 0.0))
            
            # Reserve for gas fees
            available = max(0, usdc - self.gas_reserve)
            
            self.logger.debug(f"Wallet: ${usdc:.2f} total, ${available:.2f} available (${self.gas_reserve} gas reserve)")
            
            return available
        except Exception as e:
            self.logger.error(f"Error fetching balance: {e}", exc_info=True)
            return 0.0
    
    def calculate_position_size(
        self,
        recommended_stake: float,
        available_balance: float,
        current_exposure: float,
    ) -> float:
        """Calculate safe position size respecting limits.
        
        Args:
            recommended_stake: What research suggests
            available_balance: Current wallet balance (after gas reserve)
            current_exposure: Total value of active positions
            
        Returns:
            Actual stake to use (capped by balance and limits)
        """
        # Total portfolio = available + gas reserve + current exposure
        # (available_balance is already after gas reserve, so add it back for portfolio calc)
        total_portfolio = available_balance + self.gas_reserve + current_exposure
        
        # Max 5% per position (configurable)
        max_position_pct = getattr(self.config, 'autopilot', None)
        if max_position_pct and hasattr(max_position_pct, 'max_position_pct'):
            max_pct = max_position_pct.max_position_pct
        else:
            max_pct = 0.05  # Default 5%
        
        max_position = total_portfolio * max_pct
        
        # Cap by capital utilization (default 80%)
        capital_util = 0.80
        if max_position_pct and hasattr(max_position_pct, 'capital_utilization'):
            capital_util = max_position_pct.capital_utilization
        
        max_spendable = available_balance * capital_util
        
        # Use minimum of all constraints
        actual_stake = min(
            recommended_stake,
            max_position,
            max_spendable,
            available_balance  # Can't spend more than we have
        )
        
        actual_stake = max(0, actual_stake)
        
        if actual_stake < recommended_stake:
            self.logger.info(
                f"Position size capped: Recommended ${recommended_stake:.2f} → "
                f"Actual ${actual_stake:.2f} (balance: ${available_balance:.2f}, "
                f"max_position: ${max_position:.2f})"
            )
        
        return actual_stake

