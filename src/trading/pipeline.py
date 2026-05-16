"""High-level pipeline helpers for propose / risk / execute."""
from __future__ import annotations

from typing import List

from src.trading.config import TradingConfig
from src.trading.market_data import MarketDataBundle, load_panel
from src.trading.models import OrderProposal, PortfolioState, Position, save_proposals, proposals_path
from src.trading.oms.order_manager import OrderManager, get_broker, portfolio_from_broker
from src.trading.signals.placeholder import PlaceholderStrategy


def build_proposals(
    config: TradingConfig,
    asof_date: str,
    strategy: PlaceholderStrategy | None = None,
) -> List[OrderProposal]:
    config.ensure_dirs()
    market = load_panel(asof_date=asof_date)
    broker = get_broker(config)
    broker.login()
    portfolio = portfolio_from_broker(broker, asof_date)

    strat = strategy or PlaceholderStrategy()
    signals = strat.generate_signals(market, portfolio)

    proposals: List[OrderProposal] = []
    for sig in signals:
        adv = market.adv50_at(sig.symbol, asof_date)
        prop = OrderProposal(
            signal=sig,
            adv50_vnd=adv,
            nav_vnd=portfolio.nav_vnd,
        )
        proposals.append(prop)

    path = proposals_path(config.data_root, asof_date)
    save_proposals(path, proposals)
    return proposals
