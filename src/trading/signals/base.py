"""Strategy interface — deterministic signals only."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.trading.market_data import MarketDataBundle
from src.trading.models import PortfolioState, Signal


class BaseStrategy(ABC):
    name: str = "base"

    @abstractmethod
    def generate_signals(
        self,
        market_data: MarketDataBundle,
        portfolio_state: PortfolioState,
    ) -> List[Signal]:
        """Produce trade signals from market data and current holdings."""
