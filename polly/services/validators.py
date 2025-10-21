"""Validation and safety checks for trade execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polly.models import Market

if TYPE_CHECKING:
    from polly.services.trading import TradingService


def validate_trade_size(
    size: float, available_balance: float, max_risk_pct: float, stake: float
) -> tuple[bool, str]:
    """Validate trade size against available balance and risk limits.

    Args:
        size: Number of shares to trade
        available_balance: Available cash balance
        max_risk_pct: Maximum risk percentage per trade (0.0-1.0)
        stake: Dollar amount of the trade

    Returns:
        Tuple of (is_valid, error_message)
    """
    if size <= 0:
        return False, "Trade size must be greater than 0"

    if stake <= 0:
        return False, "Stake amount must be greater than 0"

    # Check if stake exceeds available balance
    if stake > available_balance:
        return False, f"Insufficient balance: ${stake:.2f} required, ${available_balance:.2f} available"

    # Check if stake exceeds risk limit
    max_stake = available_balance * max_risk_pct
    if stake > max_stake:
        return (
            False,
            f"Trade exceeds risk limit: ${stake:.2f} > ${max_stake:.2f} ({max_risk_pct*100:.1f}% of balance)",
        )

    return True, ""


def validate_token_id(token_id: str, market: Market) -> bool:
    """Ensure token_id is valid for the market.

    Args:
        token_id: Token ID to validate
        market: Market object

    Returns:
        True if token_id exists in market, False otherwise
    """
    if not token_id:
        return False

    # Check if token_id exists in market outcomes
    valid_token_ids = [outcome.token_id for outcome in market.outcomes]
    return token_id in valid_token_ids


def check_usdc_balance(trading_service: TradingService, required: float) -> tuple[bool, str]:
    """Check if user has sufficient USDC balance.

    Args:
        trading_service: Trading service instance
        required: Required USDC amount

    Returns:
        Tuple of (is_sufficient, error_message)
    """
    try:
        balances = trading_service.get_balances()

        if "error" in balances:
            return False, f"Error fetching balance: {balances['error']}"

        # Extract USDC balance (exact key depends on API response structure)
        usdc_balance = balances.get("usdc", 0.0)

        if usdc_balance < required:
            return False, f"Insufficient USDC: ${required:.2f} required, ${usdc_balance:.2f} available"

        return True, ""

    except Exception as e:
        return False, f"Error checking balance: {str(e)}"


def validate_market_active(market: Market) -> tuple[bool, str]:
    """Validate that market is still active and tradeable.

    Args:
        market: Market object

    Returns:
        Tuple of (is_active, error_message)
    """
    from datetime import datetime, timezone

    now = datetime.now(tz=timezone.utc)

    if market.end_date <= now:
        return False, "Market has expired and is no longer tradeable"

    # Check if market has valid outcomes with prices
    if not market.outcomes:
        return False, "Market has no tradeable outcomes"

    # Check if outcomes have valid prices
    for outcome in market.outcomes:
        if outcome.price <= 0 or outcome.price >= 1:
            return False, f"Invalid price for outcome '{outcome.outcome}': {outcome.price}"

    return True, ""

