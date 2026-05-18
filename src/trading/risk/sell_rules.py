"""Risk-reducing SELL exit rules — do not apply BUY sizing caps."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.trading.config import LiveTradingConfig
from src.trading.models import OrderProposal, OrderSide, PortfolioState, RiskDecision

RuleResult = Tuple[bool, str, str, RiskDecision]


def _is_sell_exit(proposal: OrderProposal) -> bool:
    action = str(proposal.signal.metadata.get("action", ""))
    return (
        proposal.signal.side.upper() == OrderSide.SELL.value
        or action in ("SELL_TP1", "SELL_EXIT")
    )


def check_sell_position_exists(proposal: OrderProposal, portfolio: PortfolioState) -> RuleResult:
    sym = proposal.signal.symbol
    held = portfolio.position_map().get(sym)
    qty = held.quantity if held else 0
    if qty <= 0:
        return False, "sell_no_position", f"No position for {sym}", RiskDecision.BLOCK
    if proposal.signal.quantity > qty:
        return (
            False,
            "sell_qty_exceeds_position",
            f"Sell qty {proposal.signal.quantity} > held {qty}",
            RiskDecision.BLOCK,
        )
    return True, "sell_position", "", RiskDecision.PASS


def check_sell_order_value_sane(proposal: OrderProposal) -> RuleResult:
    val = proposal.order_value_vnd
    if val <= 0:
        return False, "sell_value", "Sell order value must be positive", RiskDecision.BLOCK
    return True, "sell_value", "", RiskDecision.PASS


def check_sell_data_health(extra: Dict[str, Any], cfg: LiveTradingConfig) -> RuleResult:
    if not cfg.require_data_health:
        return True, "data_health", "", RiskDecision.PASS
    hs = extra.get("data_health", {})
    if hs.get("BLOCK_ORDER_GENERATION") or hs.get("status") == "CRITICAL_FAIL":
        return False, "data_health", "Data health CRITICAL_FAIL blocks exit", RiskDecision.BLOCK
    return True, "data_health", "", RiskDecision.PASS


def check_sell_kill_switch(extra: Dict[str, Any], cfg: LiveTradingConfig) -> RuleResult:
    if not cfg.block_on_kill_switch:
        return True, "kill_switch", "", RiskDecision.PASS
    ks = extra.get("kill_switch", {})
    if ks.get("status") != "BLOCK":
        return True, "kill_switch", "", RiskDecision.PASS
    reason = str(ks.get("reason", "")).lower()
    # Allow risk-reducing sells when block is only regime/market-risk related
    if cfg.allow_risk_reducing_sell_when_regime_blocked and any(
        x in reason for x in ("regime", "bear", "vnindex")
    ):
        return (
            False,
            "kill_switch_regime",
            "Regime-related kill switch — manual review for exit",
            RiskDecision.MANUAL_REVIEW,
        )
    return False, "kill_switch", ks.get("reason", "kill switch active"), RiskDecision.BLOCK


def check_sell_reconciliation(extra: Dict[str, Any], cfg: LiveTradingConfig) -> RuleResult:
    rs = extra.get("reconciliation", {})
    if not rs.get("BLOCK_NEW_ORDERS"):
        return True, "reconciliation", "", RiskDecision.PASS
    if cfg.block_sell_on_dirty_reconciliation:
        return (
            False,
            "reconciliation",
            "Dirty reconciliation — exit manual review",
            RiskDecision.MANUAL_REVIEW,
        )
    return True, "reconciliation", "", RiskDecision.PASS


def check_sell_stale_scan(proposal: OrderProposal, extra: Dict[str, Any]) -> RuleResult:
    hs = extra.get("data_health", {})
    scan = hs.get("scan_resolve", {})
    if scan.get("is_stale"):
        return False, "stale_scan", "Stale scan for exit", RiskDecision.MANUAL_REVIEW
    return True, "stale_scan", "", RiskDecision.PASS


def _pass(rule_id: str) -> RuleResult:
    return True, rule_id, "", RiskDecision.PASS


def check_sell_liquidity_warn(proposal: OrderProposal, cfg: LiveTradingConfig) -> RuleResult:
    if cfg.sell_exit_liquidity_policy not in ("warn_only",):
        return True, "sell_liquidity", "", RiskDecision.PASS
    adv = proposal.adv50_vnd
    if adv > 0 and proposal.order_value_vnd / adv > cfg.max_order_pct_adv50:
        return (
            False,
            "sell_adv_warn",
            "Large exit vs ADV — liquidity warning",
            RiskDecision.MANUAL_REVIEW,
        )
    return True, "sell_liquidity", "", RiskDecision.PASS


def evaluate_sell_rules(
    proposal: OrderProposal,
    portfolio: PortfolioState,
    cfg: LiveTradingConfig,
    extra: Dict[str, Any],
    pending_keys: List[str],
) -> Tuple[List[str], List[str], RiskDecision]:
    """Returns (reasons, rule_ids, decision)."""
    from src.trading.risk import rules as R

    def _buy_rule(fn, *args) -> RuleResult:
        ok, rid, msg = fn(*args)
        return ok, rid, msg, RiskDecision.PASS if ok else RiskDecision.BLOCK

    checks: List[RuleResult] = [
        check_sell_position_exists(proposal, portfolio),
        check_sell_order_value_sane(proposal),
        check_sell_data_health(extra, cfg),
        check_sell_kill_switch(extra, cfg),
        check_sell_reconciliation(extra, cfg),
        check_sell_stale_scan(proposal, extra),
        _buy_rule(R.check_no_duplicate_open_orders, proposal, portfolio, pending_keys),
        _buy_rule(R.check_stale_market_data, proposal, cfg),
    ]
    liq = check_sell_liquidity_warn(proposal, cfg)
    if not liq[0] and liq[3] == RiskDecision.MANUAL_REVIEW:
        checks.append(liq)

    manual_mr = False
    reasons_mr: List[str] = []
    rules_mr: List[str] = []
    reasons_block: List[str] = []
    rules_block: List[str] = []

    for ok, rule_id, msg, dec in checks:
        if ok or not msg:
            continue
        if dec == RiskDecision.MANUAL_REVIEW:
            manual_mr = True
            reasons_mr = [msg]
            rules_mr = [rule_id]
        else:
            reasons_block.append(msg)
            rules_block.append(rule_id)

    if reasons_block:
        return reasons_block, rules_block, RiskDecision.BLOCK
    if manual_mr:
        return reasons_mr, rules_mr, RiskDecision.MANUAL_REVIEW
    return [], [], RiskDecision.PASS
