"""Live-workflow pre-trade rules."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from src.trading.config import LiveTradingConfig
from src.trading.models import OrderProposal, OrderSide, PortfolioState, RiskDecision

RuleResult = Tuple[bool, str, str, RiskDecision]  # ok, rule_id, msg, decision_if_fail


def check_max_daily_orders(portfolio: PortfolioState, cfg: LiveTradingConfig) -> RuleResult:
    if portfolio.daily_orders >= cfg.max_daily_orders:
        return False, "max_daily_orders", f"daily_orders {portfolio.daily_orders} >= {cfg.max_daily_orders}", RiskDecision.BLOCK
    return True, "max_daily_orders", "", RiskDecision.PASS


def check_max_slots(proposal: OrderProposal, portfolio: PortfolioState, cfg: LiveTradingConfig) -> RuleResult:
    if proposal.signal.side.upper() != OrderSide.BUY.value:
        return True, "max_slots", "", RiskDecision.PASS
    sym = proposal.signal.symbol
    if sym in portfolio.position_map():
        return True, "max_slots", "", RiskDecision.PASS
    if len(portfolio.positions) >= cfg.max_slots:
        return False, "max_slots", f"open slots {len(portfolio.positions)} >= {cfg.max_slots}", RiskDecision.BLOCK
    return True, "max_slots", "", RiskDecision.PASS


def check_data_health(extra: Dict[str, Any], cfg: LiveTradingConfig) -> RuleResult:
    if not cfg.require_data_health:
        return True, "data_health", "", RiskDecision.PASS
    hs = extra.get("data_health", {})
    if hs.get("BLOCK_ORDER_GENERATION") or hs.get("status") == "CRITICAL_FAIL":
        return False, "data_health", "Data health CRITICAL_FAIL", RiskDecision.BLOCK
    return True, "data_health", "", RiskDecision.PASS


def check_kill_switch(extra: Dict[str, Any], cfg: LiveTradingConfig) -> RuleResult:
    if not cfg.block_on_kill_switch:
        return True, "kill_switch", "", RiskDecision.PASS
    ks = extra.get("kill_switch", {})
    if ks.get("status") == "BLOCK":
        return False, "kill_switch", ks.get("reason", "kill switch active"), RiskDecision.BLOCK
    return True, "kill_switch", "", RiskDecision.PASS


def check_reconciliation(extra: Dict[str, Any], cfg: LiveTradingConfig) -> RuleResult:
    if not cfg.require_reconciliation_clean:
        return True, "reconciliation", "", RiskDecision.PASS
    rs = extra.get("reconciliation", {})
    if rs.get("BLOCK_NEW_ORDERS"):
        return False, "reconciliation", "Reconciliation BLOCK_NEW_ORDERS", RiskDecision.BLOCK
    return True, "reconciliation", "", RiskDecision.PASS


def check_regime_bull(proposal: OrderProposal, cfg: LiveTradingConfig) -> RuleResult:
    if not cfg.require_regime_bull:
        return True, "regime_bull", "", RiskDecision.PASS
    if proposal.signal.side.upper() != OrderSide.BUY.value:
        return True, "regime_bull", "", RiskDecision.PASS
    tier = proposal.signal.metadata.get("tier", "")
    if tier not in ("T1", "T2", ""):
        return True, "regime_bull", "", RiskDecision.PASS
    if not proposal.signal.metadata.get("regime_bull", True):
        return False, "regime_bull", "VNINDEX regime not bull", RiskDecision.BLOCK
    return True, "regime_bull", "", RiskDecision.PASS


def check_breadth_manual_review(proposal: OrderProposal) -> RuleResult:
    if proposal.signal.metadata.get("requires_manual_review"):
        return False, "breadth_defense", "Breadth defense — manual review required", RiskDecision.MANUAL_REVIEW
    if proposal.signal.metadata.get("action") == "BUY_T1_MANUAL_REVIEW":
        return False, "breadth_defense", "T1 manual review", RiskDecision.MANUAL_REVIEW
    return True, "breadth_defense", "", RiskDecision.PASS


def check_pts_s3_block(proposal: OrderProposal, cfg: LiveTradingConfig) -> RuleResult:
    action = proposal.signal.metadata.get("action", "")
    if "PTS" in action and not cfg.allow_pts_shadow:
        return False, "pts_shadow", "PTS shadow — no capital order", RiskDecision.BLOCK
    if "S3" in action and not cfg.allow_s3_capital:
        return False, "s3_research", "S3 research only", RiskDecision.BLOCK
    return True, "pts_s3", "", RiskDecision.PASS
