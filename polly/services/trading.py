from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class TradingGateway(ABC):
    @abstractmethod
    def place_order(
        self,
        *,
        poll_id: str,
        outcome_id: str,
        side: str,
        size_usdc: float,
        research_id: Optional[str] = None,
        limit_price: Optional[float] = None,
    ) -> str:
        """Place an order and return internal trade ID."""

    @abstractmethod
    def cancel_order(self, trade_id: str) -> None:
        """Cancel an order if supported (noop for paper)."""

    @abstractmethod
    def refresh_fills(self, trade_id: str) -> None:
        """Update trade state from provider (noop for paper)."""


