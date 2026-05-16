"""Placeholder strategy for pipeline integration tests."""
from __future__ import annotations

import os
from typing import List

from src.trading.market_data import MarketDataBundle
from src.trading.models import OrderSide, PortfolioState, Signal
from src.trading.signals.base import BaseStrategy


class PlaceholderStrategy(BaseStrategy):
    """
    Default: no signals.
    If TRADING_PLACEHOLDER_SYMBOL is set, emit one small BUY for integration.
    """

    name = "placeholder"

    def generate_signals(
        self,
        market_data: MarketDataBundle,
        portfolio_state: PortfolioState,
    ) -> List[Signal]:
        sym = os.environ.get("TRADING_PLACEHOLDER_SYMBOL", "").strip().upper()
        if not sym:
            return []

        close = market_data.close_at(sym, market_data.asof_date)
        if close <= 0:
            return []

        # Small test size: 100 shares
        qty = 100
        return [
            Signal(
                strategy=self.name,
                symbol=sym,
                side=OrderSide.BUY.value,
                asof_date=market_data.asof_date,
                intended_price=close,
                quantity=qty,
                reason="placeholder_integration",
            )
        ]
