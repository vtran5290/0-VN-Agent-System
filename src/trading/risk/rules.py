"""Individual risk rules — each returns (passed, rule_id, message)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from src.trading.config import TradingConfig
from src.trading.models import OrderProposal, OrderSide, PortfolioState


RuleResult = Tuple[bool, str, str]


def check_max_order_value(proposal: OrderProposal, cfg: TradingConfig) -> RuleResult:
    val = proposal.order_value_vnd
    if val > cfg.max_order_value_vnd:
        return (
            False,
            "max_order_value_vnd",
            f"Order value {val:,.0f} VND exceeds max {cfg.max_order_value_vnd:,.0f}",
        )
    return True, "max_order_value_vnd", ""


def check_min_adv50(proposal: OrderProposal, cfg: TradingConfig) -> RuleResult:
    adv = proposal.adv50_vnd
    if adv < cfg.min_adv50_vnd:
        return (
            False,
            "min_adv50_vnd",
            f"ADV50 {adv:,.0f} VND below min {cfg.min_adv50_vnd:,.0f}",
        )
    return True, "min_adv50_vnd", ""


def check_max_order_pct_adv50(proposal: OrderProposal, cfg: TradingConfig) -> RuleResult:
    adv = proposal.adv50_vnd
    if adv <= 0:
        return False, "max_order_pct_adv50", "ADV50 missing or zero"
    pct = proposal.order_value_vnd / adv
    if pct > cfg.max_order_pct_adv50:
        return (
            False,
            "max_order_pct_adv50",
            f"Order {pct:.2%} of ADV50 exceeds max {cfg.max_order_pct_adv50:.2%}",
        )
    return True, "max_order_pct_adv50", ""


def check_max_position_pct_nav(
    proposal: OrderProposal, portfolio: PortfolioState, cfg: TradingConfig
) -> RuleResult:
    nav = portfolio.nav_vnd or proposal.nav_vnd
    if nav <= 0:
        return False, "max_position_pct_nav", "NAV is zero or unknown"
    sym = proposal.signal.symbol
    existing = portfolio.position_map().get(sym)
    existing_mv = existing.market_value_vnd if existing else 0.0
    if proposal.signal.side.upper() == OrderSide.SELL.value:
        return True, "max_position_pct_nav", ""
    new_mv = existing_mv + proposal.order_value_vnd
    pct = new_mv / nav
    if pct > cfg.max_position_pct_nav:
        return (
            False,
            "max_position_pct_nav",
            f"Position {sym} would be {pct:.2%} of NAV, max {cfg.max_position_pct_nav:.2%}",
        )
    return True, "max_position_pct_nav", ""


def check_max_total_exposure(
    proposal: OrderProposal, portfolio: PortfolioState, cfg: TradingConfig
) -> RuleResult:
    nav = portfolio.nav_vnd or proposal.nav_vnd
    if nav <= 0:
        return False, "max_total_exposure_pct_nav", "NAV is zero or unknown"
    exposure = portfolio.total_exposure_vnd()
    if proposal.signal.side.upper() == OrderSide.BUY.value:
        exposure += proposal.order_value_vnd
    elif proposal.signal.side.upper() == OrderSide.SELL.value:
        exposure = max(0.0, exposure - proposal.order_value_vnd)
    pct = exposure / nav
    if pct > cfg.max_total_exposure_pct_nav:
        return (
            False,
            "max_total_exposure_pct_nav",
            f"Total exposure {pct:.2%} exceeds max {cfg.max_total_exposure_pct_nav:.2%}",
        )
    return True, "max_total_exposure_pct_nav", ""


def check_max_daily_new_positions(
    proposal: OrderProposal, portfolio: PortfolioState, cfg: TradingConfig
) -> RuleResult:
    if proposal.signal.side.upper() != OrderSide.BUY.value:
        return True, "max_daily_new_positions", ""
    sym = proposal.signal.symbol
    if sym in portfolio.position_map():
        return True, "max_daily_new_positions", ""
    if portfolio.new_positions_today >= cfg.max_daily_new_positions:
        return (
            False,
            "max_daily_new_positions",
            f"Already {portfolio.new_positions_today} new positions today, max {cfg.max_daily_new_positions}",
        )
    return True, "max_daily_new_positions", ""


def check_no_margin(
    proposal: OrderProposal, portfolio: PortfolioState, cfg: TradingConfig
) -> RuleResult:
    if cfg.allow_margin:
        return True, "no_margin", ""
    if proposal.signal.side.upper() != OrderSide.BUY.value:
        return True, "no_margin", ""
    cost = proposal.order_value_vnd
    if cost > portfolio.cash_vnd:
        return (
            False,
            "no_margin",
            f"Insufficient cash {portfolio.cash_vnd:,.0f} for order {cost:,.0f} (margin disabled)",
        )
    return True, "no_margin", ""


def check_no_duplicate_open_orders(
    proposal: OrderProposal, portfolio: PortfolioState, pending_keys: List[str]
) -> RuleResult:
    sym = proposal.signal.symbol
    side = proposal.signal.side.upper()
    for o in portfolio.open_orders:
        if o.get("symbol") == sym and o.get("side", "").upper() == side:
            if o.get("state") not in ("FILLED", "CANCELLED", "REJECTED_BY_RISK", "BROKER_REJECTED"):
                return (
                    False,
                    "no_duplicate_open_orders",
                    f"Open order exists for {sym} {side}",
                )
    key = proposal.idempotency_key
    if key in pending_keys:
        return False, "no_duplicate_open_orders", f"Duplicate idempotency key {key}"
    return True, "no_duplicate_open_orders", ""


def check_stale_market_data(proposal: OrderProposal, cfg: TradingConfig) -> RuleResult:
    asof = proposal.signal.asof_date[:10]
    meta = proposal.signal.metadata or {}
    latest_panel = str(meta.get("latest_panel_date", ""))[:10]

    if not asof:
        return False, "stale_market_data", "Invalid empty asof_date"

    if latest_panel:
        if latest_panel == asof:
            return True, "stale_market_data", ""
        if latest_panel > asof:
            return (
                False,
                "stale_market_data",
                f"latest_panel_date {latest_panel} newer than asof {asof}",
            )
        # panel older than asof — fall through to hour check with warning in metadata
        meta["stale_data_fallback_used"] = True
        proposal.signal.metadata = meta

    try:
        asof_dt = datetime.strptime(asof, "%Y-%m-%d")
    except ValueError:
        return False, "stale_market_data", f"Invalid asof_date: {asof}"

    from datetime import UTC
    age_h = (datetime.now(UTC).replace(tzinfo=None) - asof_dt).total_seconds() / 3600.0
    if age_h > cfg.market_data_max_age_hours:
        msg = f"Market data age {age_h:.1f}h exceeds max {cfg.market_data_max_age_hours}h"
        if meta.get("stale_data_fallback_used"):
            msg += " (fallback; latest_panel_date missing or stale)"
        return False, "stale_market_data", msg
    return True, "stale_market_data", ""
